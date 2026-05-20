import time

def ram_doldur(gb_miktari):
    try:
        print(f"{gb_miktari} GB RAM ayrılıyor... Lütfen bekleyin.")
        # Her 1 GB yaklaşık 1024^3 byte'tır.
        # bytearray kullanarak RAM'de yer ayırıyoruz.
        veri = bytearray(gb_miktari * 1024 * 1024 * 1024)
        
        print("RAM başarıyla dolduruldu. Durdurmak için CTRL+C yapın.")
        while True:
            time.sleep(1) # Programın kapanmaması için döngüde tutuyoruz
    except MemoryError:
        print("Hata: Sistemde bu kadar boş RAM bulunamadı!")
    except KeyboardInterrupt:
        print("\nİşlem durduruldu, RAM serbest bırakılıyor.")

if __name__ == "__main__":
    # Buradaki sayıyı ihtiyacınıza göre değiştirebilirsiniz
    ram_doldur(40)