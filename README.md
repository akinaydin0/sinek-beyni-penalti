# Sinek beyni penaltı atıyor: doğrulama deposu

Gerçek bir meyve sineğinin beyin haritasından kurulan model, Uğurcan Çakır adlı simüle bir kaleciye 5 penaltı attı.
Final koşu 23 Ekim 2026'da yapıldı (run_id `FINAL-a8f0cfde20`, drand turu 33311502) ve sonuç **SİNEK 5 – 0 ÇAKIR**
oldu. Sonucu ben seçmedim. Bu depo, bunu kendi bilgisayarında kontrol edebilmen için var.

[English version below](#english)

## Kendin doğrula

Dört komutla kurar ve provayı doğrularsın, beşincisiyle final koşuyu.

### Gerekenler

| | Windows 10/11 | macOS (Apple Silicon / Intel) | Linux (Ubuntu 24.04) |
|---|---|---|---|
| Python 3.12 (referans 3.12.10) | python.org'dan 3.12 kurucusu ("py launcher" ile) | `brew install python@3.12` ya da python.org | `sudo apt install python3.12 python3.12-venv python3.12-dev` |
| C/C++ derleyici (Brian2 Cython) | "Build Tools for Visual Studio 2022" → *Desktop development with C++* | `xcode-select --install` | `sudo apt install build-essential` |
| git | git-scm.com | Xcode araçlarıyla gelir | `sudo apt install git` |
| Node.js (isteğe bağlı) | nodejs.org | `brew install node` | `sudo apt install nodejs` |

Disk: ~1 GB (beyin ortamı ~530 MB, model verisi ~104 MB). İnternet: paketler, model verisi ve drand relay'leri için.
Node.js isteğe bağlı: varsa `verify.py` ayrı yazılmış bir JavaScript kontrolünü de çalıştırır, yoksa atlar.

**Derleyici şart.** `beyin/beyin_model.py` Brian2'yi `cython` hedefine sabitler. Derleyici yoksa Brian2 numpy'ye
**geçmez**: beyin koşusu hata verir, doğrulama "DOĞRULANAMADI" der ve sorun gizli kalmaz (CI'da ölçüldü).
`araclar/kur.py` en sonda küçük bir derleme denemesi yapar, eksik varsa ne kuracağını söyler.

### Dört komut

Her adım bir Python betiği, kabuk betiği yok. `-I`, Python'u ortam değişkenlerinden ve bulunduğu klasördeki
dosyalardan yalıtır.

**Windows (PowerShell)**

```powershell
git clone https://github.com/akinaydin0/sinek-beyni-penalti.git
cd sinek-beyni-penalti
py -3.12 -I araclar\kur.py          # 1) kurulum: beyin\.venv, birebir paket sürümleri, derleme denemesi
py -3.12 -I araclar\veri_indir.py   # 2) Shiu et al. model dosyaları (~104 MB) + SHA-256 kontrolü
py -3.12 -I araclar\testler.py      # 3) dosya özetleri, duyuru özeti, 34 test
py -3.12 -I araclar\dogrula.py      # 4) PROVA9B'yi beyin yeniden koşusuyla doğrula
```
`py` komutu yoksa (Python'u Microsoft Store'dan kurduysan) `python` yaz; `python --version` 3.12 göstermeli.

**macOS ve Linux (Terminal)**

```bash
git clone https://github.com/akinaydin0/sinek-beyni-penalti.git
cd sinek-beyni-penalti
python3.12 -I araclar/kur.py
python3.12 -I araclar/veri_indir.py
python3.12 -I araclar/testler.py
python3.12 -I araclar/dogrula.py
```

### Beklenen sonuç (PROVA9B)

`dogrula.py` tek başına çalışınca PROVA9B'yi doğrular. PROVA9B bir prova: skoru da SİNEK 5 – 0 ÇAKIR, ama final sonuç
o değil.

```
sinek beyni: 5 şutun 5'inde spike'lar Mac referansıyla BİT BİT AYNI
verify.py sonucu: PROVA DOĞRULANDI (final sonuç DEĞİL) (çıkış 3)
```
- "PROVA DOĞRULANDI" provanın tuttuğunu söyler, final sonucun değil (çıkış kodu 3).
- 1 UYARI normal: provada taahhüt turdan yalnız 4 dakika önceydi (finalde en az 120 dk).
- Akın'ın Mac'i dışında 1 UYARI daha çıkar: "beyin ortamı taahhüttekinden farklı". Sebebi platform adı
  (ör. `Windows-…`). Paket sürümleri aynı; Windows'ta Brian2 fazladan `py-cpuinfo` kurar, o kadar. Spike'lar yine
  birebir karşılaştırılır.
- İlk koşu uzun sürer: Brian2 ağın kodunu bir kez derler. Önbellek: Windows `%USERPROFILE%\.cython`, macOS
  `~/Library/Caches/cython`, Linux `~/.cython` (`CYTHON_CACHE_DIR` ile değişir).
- **`verify.py`'yi `dogrula.py` üzerinden çalıştır.** `dogrula.py` beyin Python'una UTF-8 kalkanı verir
  (`beyin/.venv/bin/python_utf8`, Windows'ta `beyin\.venv\python_utf8.cmd`). `oyun/verify.py`'yi doğrudan
  çalıştıracaksan `-X utf8` ve `--beyin-python` ile bu kalkan şart; yoksa 8-bit kod sayfalı Windows'ta (ör. Türkçe
  cp1254) beyin ya da JavaScript kontrolünün çıktısı yanlış çözülür, sonuç DOĞRULANAMADI olur.
- Beyin koşturulamazsa `dogrula.py` sebebi düz dille yazar (`NEDEN:` satırı).

### Final koşuyu doğrula

Üç değeri **kendin**, dış bir kaynaktan oku: `--kod`, `--duyuru-sha` ve `--yayin-utc`. Üçü de Bölüm 1 reel'inin
altındaki yorumda (<https://www.instagram.com/reel/Dewx1Urt9bb/>):

- `--kod`: yorumdaki "Taahhüt (SHA-256)" satırı (TAM SHA-256)
- `--duyuru-sha`: "Kurallar + kod özeti" satırı
- `--yayin-utc`: yorumun Instagram'daki saati, UTC (ör. `2026-10-23T12:04:00Z`)

Bunları depodaki dosyalardan okuma, çünkü operatörün elindeki dosyalar kanıt değildir. Git commit tarihi de kanıt
değildir: commit'i yapan onu istediği gibi yazabilir.

macOS / Linux:
```bash
python3.12 -I araclar/dogrula.py --taahhut veri/taahhut.json --config oyun/config_final.json \
    --log veri/penalty_log.json --karar veri/beyin_kararlari.json --beacon-dosya veri/beacon.json \
    --kod <TAM_64_KARAKTER_SHA256> --duyuru-sha <DUYURU_OZETI> --yayin-utc <ILK_GORULME_UTC>
```
Windows (PowerShell):
```powershell
py -3.12 -I araclar\dogrula.py --taahhut veri\taahhut.json --config oyun\config_final.json `
    --log veri\penalty_log.json --karar veri\beyin_kararlari.json --beacon-dosya veri\beacon.json `
    --kod <TAM_64_KARAKTER_SHA256> --duyuru-sha <DUYURU_OZETI> --yayin-utc <ILK_GORULME_UTC>
```
Beklenen son satır: `SONUÇ: DOĞRULANDI` (çıkış 0) ve "5 şutun 5'inde spike'lar Mac referansıyla BİT BİT AYNI".
Akın'ın Mac'indeki çıktı `veri/final_verify_cikti.txt` içinde; kanıt değil, karşılaştırman için.

Ayrı yazılmış JavaScript kontrolü yalnız Node.js ister ve `BAĞIMSIZ KONTROL: TUTUYOR` demeli. `dogrula.py` bunu kendi
içinde de çalıştırır.
```bash
node oyun/bagimsiz/kontrol.mjs veri/beacon.json veri/taahhut.json veri/penalty_log.json veri/beyin_kararlari.json
```
Windows'ta aynı komut ters bölüyle: `node oyun\bagimsiz\kontrol.mjs veri\beacon.json veri\taahhut.json veri\penalty_log.json veri\beyin_kararlari.json`.

`oyun/verify.py` dondurulduğu için çıktısında eski plandan kalan sözler geçer ("story/sabitlenmiş gönderideki TAM
SHA-256", "önceden duyurulan"); bu koşuda ikisinin de kaynağı o yorum. `araclar/dogrula.py` onu **değiştirmeden**
çağırır. İstersen doğrudan da çalıştırabilirsin: `python3.12 -I -X utf8 oyun/verify.py --help`.

## Doğrulama neyi kanıtlar

"Sonuç seçilmedi" demek için üç şeyin birlikte tutması gerekir. Biri eksikse "DOĞRULANDI" ekranı tek başına bir şey
kanıtlamaz.

1. **Taahhüt önceden herkese açıktı.** Bunu program bilemez. Bölüm 1 reel'inin altındaki yorumun Instagram'daki
   saatini **sen** okursun ve `--yayin-utc` ile verirsin. **Sınır:** bu koşuda zamanın tek kanıtı o yorumun saati;
   koşudan önce açık bir depo ya da bağımsız bir zaman damgası yoktu.
2. **drand imzası geçerli.** Sahte bir rastgele değer, internet taklit edilse bile BLS kontrolünden geçmez.
3. **Kendi makinende yeniden koşu.** `verify.py` taahhüt ve beacon'dan tohumu ve kalecinin yerini hesaplar, beyni ve
   motoru yeniden koşturur, her sayıyı birebir karşılaştırır. Beynin bütün spike'larının özeti de buna dahil.

Akın'ın Mac'inde çekilmiş bir "DOĞRULANDI" ekranı kanıt değildir. Kanıt, **senin** indirdiğin dosyalarla kendi
makinende aldığın sonuçtur.

Bilmen gereken: kurallar sinek ölçüldükten sonra seçildi ve bu kurallarla sinek ~%99 favori (seriyi kazanma tahmini
%98,6; `oyun/olasilik.py`, `veri/olasilik_tahmini_tur4c_B.json`). Her seri adil, ama kuralların sonuçtan bağımsız
seçildiği söylenemez.

## Nasıl çalışıyor

- **Beyin:** Shiu ve ark. (Nature 2024) tüm-beyin modeli. 138.639 nöron ve 15,1 milyon bağlantı FlyWire v783 beyin
  haritasından geliyor. Brian2 ile çalışıyor (`beyin/`).
- **Sineğin gördüğü:** kalecinin yeri. Kaleci hangi taraftaysa o gözün görme nöronları (LC10) daha sık uyarılıyor.
- **Sineğin kararı:** yürürken sağa/sola döndüren 10 nöronun ve ileri iten 2 nöronun 1 saniyedeki spike sayıları.
  Önceden dondurulmuş bir formül bu sayıları nişana ve şut hızına çeviriyor (`beyin/esleme.py`, özeti `e0ff656d…`).
- **Kaleci ve top:** saf Python fizik motoru (`oyun/penalty_model.py`). Kalecinin yönü ve çıkış zamanı, şut
  bilinmeden, taahhüt edilmiş tohumlardan çekiliyor. Adı Uğurcan Çakır; değerleri EA SPORTS FC 27'nin resmi
  sayfasındaki gibi: Diving 80, Handling 76, Kicking 81, Positioning 80, Reflexes 82, boy 1,91 m.

Dürüst bulgu: sinek kaleciden kaçmıyor, ona **doğru** dönüyor (bir nesneyi takip eden sinek gibi). "Sinek kaleciyi
okuyup kandırıyor" demek yanlış olur. Ayrıntı: `beyin/README.md`.

## Kurallar

Kurallar taahhüde girer, sonradan değişemez.

- 5 şut, **her şut sayılır**, yeniden deneme yok. Gol SİNEK'e; kurtarış, direk, aut ve üstten aut ÇAKIR'a. Direğe
  çarpıp kale çizgisini çerçevenin içinden geçen top goldür (IFAB Kural 10; motor 1.1.1).
- **Kaleci gerçekçi (Hunter 2018):** topa dokunsa bile hızlı şut girebilir. Tutma olasılığı =
  kırp(−0,0447·hız + 1,72).
- **Kaleci gerçekçi uçar** (`balistik-v1`): ayakları yerdeyken iter, sonra serbest uçar (yerçekimi), iner ve kayar.
  Havada durmaz.
- **Şut sapması açık (seçenek B):** beynin nişanı "niyet"; ayak buna, önceden yazılmış bir formülle küçük bir
  yürütme hatası ekler (Hunter ve ark. 2018 biçimi). Ölçek maç verisine göre 0,432: böylece şutların %4,78'i kaleyi
  bulmuyor, maçlardaki penaltılar gibi. Sapma da drand turu N'den çıkar. Aut ve direk ÇAKIR'a.
- **Kaleci her şuttan önce 30–50 cm yana kayar**, yönü yarı yarıya. Sayılar drand turu N'nin rastgele değerinden
  çıkar, taahhüt anında kimse bilemez. Beyin kaleciyi tam orada görür, motor da tam oraya koyar. **Beyin tohumu da
  N'den çıkar.**
- **drand quicknet** (League of Entropy): zincir `52db9ba7…`, imza BLS12-381; `oyun/bls12381.py` imzayı kendisi
  kontrol eder.
- Kuralların ve bütün kodun tek özeti ("duyuru özeti") ile taahhüt, N yayınlanmadan **en az 120 dakika önce** herkese
  açık bir yerde durur. Bu koşuda o yer Bölüm 1 reel'inin altındaki Instagram yorumuydu (N'den yaklaşık 174 dakika
  önce). Bir gün önce ayrı duyuru yapılmadı; özet, taahhütle aynı yorumda açıklandı. Depo koşudan önce gizliydi,
  sonra açıldı.
- **Atılan her taahhüt sonuçlanır ve yayınlanır** (`veri/taahhut_gecmisi.jsonl`).

Tam akış ve formüller: `oyun/README.md`, `oyun/MODEL.md`.

## Teknik ayrıntılar

### Üç sistemde sonuç (GitHub Actions)

`.github/workflows/dogrulama.yml` her değişiklikte aynı dört adımı üç işletim sisteminde çalıştırır ve sinek beyninin
spike'larının Mac referansıyla bit bit aynı olup olmadığını raporlar. Elle tetiklenince final dosyalarını da aynı
komutlarla doğrular (macOS/Linux bash, Windows PowerShell). Son koşular: depodaki **Actions** sekmesi.

Ölçüm: **final koşu ve PROVA9B**, 2 Kasım 2026, Actions koşusu 41498877443 (Python 3.12.10, aynı 25 paket; depo
`sinek deneme ç` adlı, boşluklu ve Türkçe karakterli bir klasörde çalıştı).

| | Windows Server 2025 (x64) | macOS 26 (arm64) | Ubuntu 24.04 (x64) | Referans: Akın'ın Mac'i (M2 Pro) |
|---|---|---|---|---|
| Derleyici (Brian2 Cython) | MSVC `/Ox /arch:AVX2` | clang `-O3 -ffast-math -march=native` | gcc `-O3 -ffast-math -march=native` | clang, aynı bayraklar |
| Testler (`oyun/tests.py`) | 34/34 | 34/34 | 34/34 | 34/34 |
| Duyuru özeti | `2bf9adee…` | `2bf9adee…` | `2bf9adee…` | `2bf9adee…` |
| `verify.py` sonucu, final | **DOĞRULANDI** | **DOĞRULANDI** | **DOĞRULANDI** | DOĞRULANDI |
| `verify.py` sonucu, PROVA9B | PROVA DOĞRULANDI | PROVA DOĞRULANDI | PROVA DOĞRULANDI | PROVA DOĞRULANDI |
| Sinek beyni, final ve PROVA9B, 5'er şut | **5/5 bit bit aynı** | **5/5 bit bit aynı** | **5/5 bit bit aynı** | (referans) |
| Kontrol satırları Mac çıktısıyla, final | aynı | aynı | aynı | — |
| Bağımsız JS kontrolü, final | TUTUYOR | TUTUYOR | TUTUYOR | — |
| Brian2 numpy hedefiyle (derleyicisiz, PROVA9B) | 5/5 aynı | 5/5 aynı | 5/5 aynı | — |
| Süre/şut: cython · numpy | 4,8 s · 44,5 s | 3,1 s · 15,1 s | 4,3 s · 25,4 s | — |
| Kurulum · indirme · testler · ilk doğrulama | 73 · 4 · 16 · 72 s | 43 · 2 · 20 · 48 s | 41 · 2 · 26 · 57 s | — |

- "Bit bit aynı": her şutta bütün spike'ların (nöron numarası + zaman) SHA-256'sı, 14 nöron grubunun sayıları,
  steer, nişan, hız ve karar süresi Mac'tekiyle aynı; raster dosyaları da.
- Derleyicisiz deneme (Linux, `CC=/bin/false`, boş derleme önbelleği): **DOĞRULANAMADI**, sessizce geçmedi. CI
  sebebin derleme komutu olduğunu da kontrol eder. Hatadaki iki kez tekrarlanan
  `…/brian_extensions/…/brian_extensions/….o` yolu normal (Windows notları).
- Türkçe 8-bit yerel ayar benzetimi (Linux, ISO-8859-9, cp1254 gibi): kalkan bilerek kapatılınca **DOĞRULANAMADI**
  (`'utf-8' codec can't decode byte 0xfe`), README'deki komutla (`dogrula.py` kalkanı kendisi kullanır) PROVA
  DOĞRULANDI. Akın'ın Mac'inde de (tr_TR.ISO8859-9) ölçüldü: kalkansız DOĞRULANAMADI, varsayılanla PROVA DOĞRULANDI.
- Windows'ta Brian2 bir paket daha kurar (`py-cpuinfo==9.0.0`); `verify.py` bunu UYARI satırında gösterir.
- Önceki ölçümler: PROVA9B (23 Ekim, koşu 39892775318) ve eski kodla PROVA5 (22 Ekim), PROVA7B (23 Ekim, koşu
  39884328955 ve 39885733118) aynı üç sistemde yine 5/5 bit bit aynıydı.
- Sınır: bu, final koşunun ve PROVA9B'nin 5'er şutu ve bu CI makineleri için bir ölçüm. Başka işlemci ya da
  derleyici sürümü için kanıt değil; bu yüzden herkesten kendi makinesinde koşturması isteniyor. Tutmazsa `verify.py`
  HATA verir.

### Windows notları

- **Türkçe karakterler:** Windows konsolu ve borular cp1252/cp1254 kullanabilir. Betikler çıktıyı UTF-8'e zorlar,
  `verify.py`'yi `-X utf8` ile çalıştırır.
- **Beyin alt süreci:** `verify.py` beyni ayrı bir süreçte koşturur ve çıktısını UTF-8 diye çözer. Türkçe Windows'ta
  (cp1254) o süreç "ş" harfini tek bayt (0xFE) yazar ve çözme patlar. Bu yüzden `kur.py`
  `beyin\.venv\python_utf8.cmd` yazar: aynı Python'u `-X utf8` ile başlatır, yalnız metin kodlaması değişir.
  `dogrula.py` Windows'ta bunu kullanır. macOS ve Linux'taki eşi `beyin/.venv/bin/python_utf8` (kur.py ya da ilk
  dogrula.py yazar).
- **`beyin/.venv/bin/python`:** taahhüde giren kod beyin Python'unu bu yolda arar; Windows venv'i ise
  `Scripts\python.exe` kullanır. `kur.py` `bin\` içine bir kopya koyar. Taahhüt edilmiş koda dokunulmadı.
- **Satır sonları:** taahhüde giren dosyalar SHA-256 ile kontrol edilir. Windows git'i (core.autocrlf=true) LF'yi
  CRLF'ye çevirirse özetler tutmaz. `.gitattributes` (`* -text`) bunu kapatır; `testler.py` CRLF görürse söyler.
- **Boşluklu ve Türkçe karakterli yollar:** her yol, kabuk kullanılmadan liste hâlinde verilir. CI depoyu
  `sinek deneme ç` adlı bir klasörde çalıştırır.
- **Kullanıcı adında Türkçe karakter varsa** (ör. `C:\Users\Akın`) ve derleme yol yüzünden hata verirse, Brian2'nin
  derleme önbelleğini ASCII bir klasöre al. PowerShell'de: `$env:CYTHON_CACHE_DIR = "C:\cython_onbellek"`.
- **Derleme hatasında çift yol:** hatada `…/brian_extensions/<aynı yol>/brian_extensions/_cython_magic_….o` gibi iki
  kez tekrarlanan bir yol normaldir. setuptools ara dosyayı, kaynak dosyanın tam yolunu önbellek klasörünün altına
  ekleyerek adlandırır (başarılı derlemede de böyle). Asıl sebep derleyicinin çalışmaması.
- **python / python3.12 / py:** Python 3.12 değilse betikler durur ve doğru komutu söyler.

### Klasörler

Eski provalar da burada, çünkü atılan her taahhüt yayınlanır. Hepsi eski kodla yapıldı; bu yüzden bugünkü kodla
bilerek DOĞRULANAMADI alırlar. PROVA9B ise bugünkü kodla yapıldı.

| Yol | Ne |
|---|---|
| `oyun/` | Motor, taahhüt (`commit.py`), drand (`beacon.py`), saf Python BLS (`bls12381.py`), doğrulama (`verify.py`, `beyin_yeniden.py`), testler, bağımsız JS kontrolü (`bagimsiz/kontrol.mjs`). 11 dosya taahhüde girer. |
| `beyin/` | Sinek beyni: `kick.py`, `beyin_model.py`, `ortam.py`, `esleme.py` (DONMUŞ), `dondur.py`, `ids.json`, `DONDURMA.json` (taahhüde girer) + kalibrasyon ve kontrol betikleri. `indirilen/` boş; `veri_indir.py` doldurur. |
| `araclar/` | Kurulum ve çalıştırma kolaylığı (taahhüde girmez): `kur.py`, `veri_indir.py`, `testler.py`, `dogrula.py`; tanı aracı `beyin_hedef_olcum.py`; CI özeti `ci_ozet.py`. |
| `oyun/config_final.json`, `veri/taahhut.json`, `veri/beacon.json`, `veri/beyin_kararlari.json`, `veri/penalty_log.json` | Final koşunun dosyaları (23 Ekim 2026, run_id `FINAL-a8f0cfde20`, drand turu 33311502; SİNEK 5 – 0 ÇAKIR). |
| `veri/beyin_raster/beyin_kararlari/` | Final koşunun spike raster'ları (npz). |
| `veri/final_verify_cikti.txt` | Final koşunun Akın'ın Mac'indeki `verify.py` çıktısı. Kanıt değil; kanıt senin makinendeki sonuç. |
| `veri/prova9B/` | PROVA9B (bugünkü dondurulmuş kod: motor 1.1.1, seçenek B, ölçek 0,432; SİNEK 5 – 0 ÇAKIR): config, taahhüt, beacon, beyin kararları, penaltı log'u ve Mac'teki verify çıktısı. `dogrula.py` tek başına çalışınca bunu doğrular. |
| `veri/beyin_raster/prova9B_beyin_kararlari/` | PROVA9B'nin spike raster'ları (npz). Yolu beyin karar dosyası belirler; o dosya taahhüt zincirine bağlı olduğu için değiştirilemez. |
| `veri/ara_prova8B/` | PROVA8B (motor 1.1.1, seçenek B, eski ölçek 0,332; 5–0). Sonra sapma ölçeği yeniden kalibre edildi. |
| `veri/prova7B/` | PROVA7B (motor 1.1.0, seçenek B; 4–1) ve o günün duyurusu (`duyuru_prova7B.json`, `ab65e95b…`). Raster'ları `_tur3/veri/beyin_raster/prova7B_beyin_kararlari/`. |
| `veri/prova7A/` | PROVA7A (aynı tur, seçenek A: şut sapması kapalı; 5–0). Taahhüdü yayınlandı; seçenek A ve eski kodla yapıldığı için bugünkü şablona uymaz. |
| `veri/ara_prova6/` | Ara provalar 6A ve 6B (ikisi de 4–1). Sonra `tests.py` ve `kalibrasyon.py` değişti. |
| `veri/prova5/` | PROVA5 (22 Ekim, eski motor; 5–0) ve o günün duyurusu (`duyuru_prova5.json`, `572bbd8a…`). Motor sonra değişti (balistik kaleci, şut sapması). |
| `_tur3/veri/beyin_raster/prova5_beyin_kararlari/` | PROVA5'in spike raster'ları (npz). |
| `veri/ara_prova4/` | Ara prova 4 (3–2). Taahhüdü `veri/taahhut_gecmisi.jsonl`'da kayıtlı; sonra kod değişti. "Her taahhüt yayınlanır" kuralı gereği burada. |
| `veri/duyuru.json` | Duyuru özeti (kurallar + 21 kod/veri dosyası, seçenek B): `2bf9adee…`. |
| `veri/olasilik_tahmini_tur4c_B.json` | Kim kazanır tahmini, bugünkü kodla (20.000 seri; sonuç DEĞİL): sinek %98,6. Eski kodla yapılanlar: `..._tur4b_B`, `..._tur3b_A/B`. |
| `veri/kalibrasyon.json`, `pilot.json`, ... | Beyin kalibrasyonu ve gerçeklik kontrollerinin sonuçları (`beyin/README.md`). |

## Lisans ve atıflar

Bu projenin kodu MIT lisanslı (`LICENSE`). Shiu ve ark. modeli (MIT), FlyWire v783 verisi (CC BY 4.0), Brian2
(CeCILL 2.1) ve diğerleri bu depoda **yok**; indirilir ya da kurulur. Lisansları ve zorunlu atıflar
`THIRD_PARTY_LICENSES.md` içinde. EA'ya ait hiçbir görsel, logo ya da oyun görüntüsü kullanılmadı. Bu depoda Uğurcan
Çakır'ın yalnız adı ve resmi FC 27 değerleri var; videodaki kâğıt maske bu depoda yok. Bu proje EA, oyuncu ya da
kulübüyle bağlantılı değil.

---

<a id="english"></a>
## English

A model built from a real fruit fly's brain map took 5 penalties against a simulated keeper named Uğurcan Çakır. The
final run took place on 23 Oct 2026 (run_id `FINAL-a8f0cfde20`, drand round 33311502) and ended **FLY 5 – 0 ÇAKIR**.
I did not pick the result; this repository lets you check that on your own computer.

**How it works.** The Shiu et al. (Nature 2024) whole-brain leaky integrate-and-fire model of *Drosophila* (FlyWire
v783 connectome, 138,639 neurons, 15.1 M connections, Brian2) sees where the keeper stands, as a left/right bias on the
LC10 visual neurons, and runs for 1 s. A readout frozen before calibration turns its steering and forward-walking
descending neurons into an aim point and shot speed (`beyin/esleme.py`, digest `e0ff656d…`). A pure-Python physics
engine plays the keeper with Uğurcan Çakır's EA SPORTS FC 27 ratings (DIV 80, HAN 76, KIC 81, POS 80, REF 82). Honest
finding: the fly turns **towards** the keeper (object tracking); it does not "read and fool" him.

**Why the result was not picked.** The announcement digest (rules + all code) and the commitment went up in one
Instagram comment under the Part 1 reel, about 174 minutes before drand quicknet round N (the rule is at least 120
minutes). There was no separate announcement a day earlier, and the repository was private until after the run. The
keeper's 0.30–0.50 m shifts, the brain seed and the shot scatter all come from round N, whose BLS12-381 signature
`oyun/bls12381.py` checks. Every kick counts, every commitment made is resolved and published, and `verify.py` re-runs
the brain and the engine and compares every number, including a SHA-256 over all brain spikes.

**Verify it yourself.** You need Python 3.12, a C/C++ compiler (Brian2 is pinned to `cython` and fails loudly
without one), git and ~1 GB of disk; Node.js is optional. Run the four commands above: setup, the Shiu et al. files
from commit `91bdd1e7…` (SHA-256 checked against `beyin/ids.json`), the 34 tests plus the SHA-256 of the 21 committed
files, and `dogrula.py`, which verifies the PROVA9B dry run by default. Expected:
`PROVA DOĞRULANDI (final sonuç DEĞİL)`, exit code 3; PROVA9B also ended 5–0, but it is not the final. For the final
run use the command under "Final koşuyu doğrula" and read `--kod`, `--duyuru-sha` and `--yayin-utc` yourself from the comment under the Part 1
reel: the "Taahhüt (SHA-256)" line, the "Kurallar + kod özeti" line and the comment's timestamp. Expected:
`SONUÇ: DOĞRULANDI`, exit 0. Always go through `araclar/dogrula.py`: it gives the brain subprocess a UTF-8 launcher,
without which an 8-bit Windows code page (such as Turkish cp1254) turns the result into DOĞRULANAMADI.

**What it proves, and what it does not.** The proof is the result on *your* machine with files you downloaded, not a
"DOĞRULANDI" screenshot from mine. A git commit date is not evidence; for this run the only proof of time is that
comment's timestamp. On GitHub Actions (run 41498877443, 2 Nov 2026) Windows, macOS and Linux all gave `DOĞRULANDI`
on the final files and `PROVA DOĞRULANDI` on PROVA9B, with the brain re-run bit-identical to the Mac reference in 5 of
5 kicks. That is a measurement for those machines, not proof for every CPU or compiler. The rules were chosen after
the fly was measured, and under them the fly was a ~99% favourite (series win estimate 98.6%,
`veri/olasilik_tahmini_tur4c_B.json`).

**License.** Project code: MIT (`LICENSE`). Third-party code and data are not included; their licenses and required
citations (Shiu et al. MIT; FlyWire v783 CC BY 4.0 with Dorkenwald 2024, Schlegel 2024, Zheng 2018, Buhmann 2021,
Heinrich 2018, Eckstein 2024; Brian2 CeCILL 2.1, Stimberg 2019) are in `THIRD_PARTY_LICENSES.md`. No EA assets are
used. Not affiliated with EA, the player or his club.
