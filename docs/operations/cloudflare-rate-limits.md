# Cloudflare rate limit contract

Bu katman yalnız edge burst kontrolüdür. IP tek başına kullanıcı kimliği veya abuse
kanıtı sayılmaz; authenticated kullanıcı limitlerinin otoritesi Redis tabanlı API
katmanıdır.

Cloudflare zone `http_ratelimit` ruleset'inde aşağıdaki kurallar bu sırayla
tanımlanır. Başlangıç değerleri gerçek trafik gözlemlendikten sonra daraltılabilir.

| Ref | Expression | Characteristic | Rate | Action |
|---|---|---|---|---|
| `signup_ip` | `http.request.uri.path eq "/sign-up" and http.request.method eq "GET"` | `cf.colo.id`, `ip.src` | 10 / 60 s | Managed Challenge, 300 s |
| `preview_ip` | `http.request.uri.path eq "/api/preview/analyze" and http.request.method eq "POST"` | `cf.colo.id`, `ip.src` | 5 / 60 s | Managed Challenge, 300 s |
| `checkout_ip` | `http.request.uri.path eq "/api/billing/checkout" and http.request.method eq "POST"` | `cf.colo.id`, `ip.src` | 10 / 60 s | Block, 60 s |
| `start_job_ip` | `http.request.uri.path eq "/api/start-job" and http.request.method eq "POST"` | `cf.colo.id`, `ip.src` | 20 / 60 s | Block, 60 s |

`/api/webhooks/iyzico/subscription` ve `/api/clerk/webhooks` bu kurallara dahil
edilmez. Webhook güvenliği provider imzası ve kalıcı idempotency kaydıyla sağlanır;
IP tabanlı edge block provider retry/reconcile davranışını bozmamalıdır.

Canlı kurulumdan önce:

1. Zone'daki mevcut `http_ratelimit` entry-point ruleset içe aktarılır veya okunur;
   körlemesine üzerine yazılmaz.
2. Kurallar önce log/simülasyon imkânı olan planda gözlemlenir.
3. Origin yalnız Cloudflare üzerinden erişilebilir tutulur.
4. `429` oranı, checkout dönüşümü ve preview başarı oranı izlenir.

Cloudflare rate limiting sayaçları edge veri merkezleri arasında tam global sayaç
değildir. Bu yüzden maliyet korumasının kesin katmanı API'deki atomik Redis
limitleri ve mevcut entitlement/quota/credit reservation sırasıdır.

Production job active/pending sayıları kalıcı `jobs` kayıtlarından ve plan
kotasından hesaplanmaya devam eder. Redis `start_job` sayacı dağıtık burst'ü keser;
kalıcı job muhasebesinin yerine geçmez.
