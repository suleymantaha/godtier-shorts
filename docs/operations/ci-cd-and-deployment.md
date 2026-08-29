# CI/CD ve Production Deploy

Bu doküman `Task 23 — CI/CD` ile devreye alınan build ve deploy gate'lerini
anlatır. Amaç tek bir kural: **production'a giden tek yol, `Verify`
workflow'unun main üzerinde başarılı olmasıdır.**

## Pipeline

```text
PR
→ backend unit tests + frontend lint/test/build   (Verify / verify)
→ security + static checks                        (Verify / security)
→ Docker API build                                (Verify / docker-api)
→ Docker GPU build smoke (GPU gerektirmez)        (Verify / docker-gpu)
→ merge main
→ GHCR image publish (api + gpu)                  (Deploy / publish-*)
→ CPU control-plane release                       (Deploy / deploy)
   backup → alembic upgrade → release → health check → gerekirse rollback
```

## `Verify` workflow

`.github/workflows/verify.yml`, her push ve pull request'te çalışır.

| Job | Ne yapar |
| --- | --- |
| `verify` | PostgreSQL service container ile `scripts/verify.sh` (toolchain, runtime config, markdown link, migration safety, secret scan, frontend lint/test/build, backend pytest) |
| `security` | `pip-audit` (requirements.lock), `npm audit --audit-level=high`, destructive migration yasağı, commit'lenmiş secret taraması |
| `docker-api` | `Dockerfile.api` build eder ve image'ın CPU-only kaldığını (torch/ultralytics sızmamış) doğrular |
| `docker-gpu` | `Dockerfile.gpu` build eder. GPU runner gerektirmez; NVENC kontrolü encoder listesi üzerinden yapılır |

GPU image CUDA wheel'leri nedeniyle büyük olduğu için `docker-gpu` job'ı önce
runner diskini temizler ve GitHub Actions cache'ini kullanır.

## Static gate'ler

### Destructive migration yasağı

`scripts/check_migration_safety.py`, her Alembic dosyasının `upgrade()`
gövdesini AST ile tarar ve şunları reddeder:

- `op.drop_table`, `op.drop_column`, `op.rename_table`
- daraltıcı `op.alter_column` (`new_column_name`, `type_`, `nullable=False`)
- `op.execute` içinde `DROP TABLE` / `DROP COLUMN` / `TRUNCATE` / `RENAME TO`

`downgrade()` içindeki yıkıcı işlemler serbesttir; o yol yalnız lokal
geliştirmede kullanılır. Bu kural rollback'i mümkün kılar: yeni şema eski
image ile de çalışabildiği için health check başarısız olduğunda uygulama
geri alınabilir, veritabanı geri alınmaz.

### Commit'lenmiş secret taraması

`scripts/check_committed_secrets.py`, `git ls-files` çıktısındaki metin
dosyalarında provider formatlı token'ları (Clerk, OpenRouter, AWS, GitHub,
private key blokları) ve placeholder olmayan secret atamalarını arar.
Bilinçli istisnalar satır sonuna `# pragma: allowlist secret` ile işaretlenir.

## `Deploy` workflow

`.github/workflows/deploy.yml`, `workflow_run` ile `Verify`'ı dinler ve yalnız
`conclusion == 'success'` **ve** `head_branch == 'main'` olduğunda çalışır.
Doğrulanmış commit SHA'sı checkout edilir; hiçbir job `main`'in o anki ucuna
bakmaz.

### Yayınlanan image'lar

| Image | Tag'ler |
| --- | --- |
| `ghcr.io/<repo>-api` | `<head_sha>` (immutable), `main` |
| `ghcr.io/<repo>-gpu` | `<head_sha>` (immutable), `main` |

Release her zaman immutable SHA tag'i ile yapılır; `main` tag'i yalnız insan
kullanımı içindir.

### Release adımları

`deploy` job'ı `production` GitHub Environment'ını kullanır ve sunucuda
`scripts/deploy_production.sh` çalıştırır:

1. Mevcut api image ID'si `PREVIOUS_API_IMAGE` olarak kaydedilir.
2. `pg_dump | gzip` ile `backups/pre-deploy-<utc>.sql.gz` alınır.
3. Yeni api ve gpu image'ları pull edilir.
4. `alembic upgrade head` çalıştırılır (downgrade asla çağrılmaz).
5. Api servisi yeni image ile `up --detach` edilir.
6. `/health/ready` en fazla `HEALTH_RETRIES` (varsayılan 30) saniye beklenir.
7. Health check başarısız olursa api `PREVIOUS_API_IMAGE`'a geri alınır ve
   backup dosyasının yolu log'a yazılır.

### Gerekli secret'lar

| Secret | Açıklama |
| --- | --- |
| `DEPLOY_HOST` | CPU control-plane VPS adresi. **Tanımlı değilse deploy adımı atlanır**, image'lar yine de yayınlanır. |
| `DEPLOY_USER` | SSH kullanıcısı |
| `DEPLOY_SSH_KEY` | Deploy için ayrılmış private key (parolasız, yalnız bu iş için) |
| `DEPLOY_DIR` | Sunucudaki compose proje dizini (`compose.production.yml` ve `.env` burada) |

Registry kimlik doğrulaması `GITHUB_TOKEN` ile yapılır; ek registry secret'ı
gerekmez.

## Sunucu tarafı ön koşullar

`DEPLOY_DIR` içinde şunlar bulunmalıdır:

- `compose.production.yml`
- production `.env` (compose'un zorunlu tuttuğu tüm değişkenler)
- Docker Engine + Compose v2

`compose.production.yml` artık `API_IMAGE` ve `GPU_IMAGE` değişkenlerini
destekler; bunlar verilmediğinde lokal build tag'leri (`godtier-shorts-api:local`)
kullanılır.

## İlgili dokümanlar

- [Fresh install checklist](fresh-install-checklist.md)
- [AI session exit protocol](ai-session-exit-protocol.md)
