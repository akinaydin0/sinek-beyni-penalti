# Sinek beyni penaltı atıyor: doğrulama deposu

> **Sonucu ben seçmedim.** Bu depo, bunu kendi bilgisayarında kontrol edebilmen için var.

[English version below](#english)

> **Durum (22 Ekim 2026):** hazırlık. Final koşu **yapılmadı**. Bu depodaki tek koşu **PROVA5**, yani bir tatbikat;
> sonucu (SİNEK 5 – 0 ÇAKIR) yayımlanacak sonuç **değil**. Final günü config, taahhüt ve sonuç dosyaları buraya eklenecek.

## Bu ne?

Gerçek bir meyve sineği beyin modeli 5 penaltı atıyor. Kalecinin adı Uğurcan Çakır; değerleri EA SPORTS FC 27'nin
resmi sayfasındaki gibi: Diving 80, Handling 76, Kicking 81, Positioning 80, Reflexes 82, boy 1,91 m.

- **Beyin:** Shiu ve ark. (Nature 2024) tüm-beyin modeli. 138.639 nöron ve 15,1 milyon bağlantı FlyWire v783
  beyin haritasından geliyor. Brian2 ile çalışıyor (`beyin/`).
- **Sineğin gördüğü:** kalecinin yeri. Kaleci hangi taraftaysa o gözün görme nöronları (LC10) daha sık uyarılıyor.
- **Sineğin kararı:** 1 saniyede yürürken sağa/sola döndüren 10 nöronun ve ileri iten 2 nöronun spike sayıları.
  Bu sayılar, önceden dondurulmuş bir formülle nişana ve şut hızına çevriliyor (`beyin/esleme.py`, özeti `e0ff656d…`).
- **Kaleci ve top:** saf Python fizik motoru (`oyun/penalty_model.py`). Kalecinin yönü ve çıkış zamanı, şut
  bilinmeden, taahhüt edilmiş tohumlardan çekiliyor.

Dürüst bulgu: sinek kaleciden kaçmıyor, ona **doğru** dönüyor (bir nesneyi takip eden sinek gibi). "Sinek kaleciyi
okuyup kandırıyor" demek yanlış olur. Ayrıntı: `beyin/README.md`.

## Kurallar (taahhüde girer, sonradan değişemez)

- 5 şut atılır, **her şut sayılır**, yeniden deneme yok. Gol SİNEK'e; kurtarış, direk, aut ve üstten aut ÇAKIR'a.
- **Kaleci gerçekçi (Hunter 2018):** topa dokunsa bile hızlı şut girebilir. Tutma olasılığı = kırp(−0,0447·hız + 1,72).
- **Kaleci her şuttan önce 30–50 cm yana kayar**, yön yarı yarıya. Sayılar drand turu N'nin rastgele değerinden çıkar;
  taahhüt anında kimse bilemez. Beyin kaleciyi tam orada görür, motor tam oraya koyar.
- **Beyin tohumu da N'den çıkar.**
- **drand quicknet** (League of Entropy): zincir `52db9ba7…`, imza BLS12-381; `oyun/bls12381.py` imzayı kendisi kontrol eder.
- Kurallar ve bütün kod **bir gün önce** "duyuru özeti" ile duyurulur; taahhüt, N yayınlanmadan **en az 120 dakika önce**
  herkese açık yerde (bu depo + sabitlenmiş gönderi) durur.
- **Atılan her taahhüt sonuçlanır ve yayınlanır** (`veri/taahhut_gecmisi.jsonl`).

Tam akış ve formüller: `oyun/README.md`, `oyun/MODEL.md`.

## Doğrulama neyi kanıtlar, neyi kanıtlamaz?

Üç şey birlikte "sonuç seçilmedi" demektir. Biri eksikse "DOĞRULANDI" ekranı tek başına bir şey kanıtlamaz.

1. **Taahhüt önceden herkese açıktı.** Bunu program kendisi bilemez. Taahhüdün tur N'den önce açıkta olduğunu
   **sen** dış bir kaynaktan okursun (GitHub commit saati, sabitlenmiş gönderinin saati, OpenTimestamps) ve
   `--yayin-utc` olarak verirsin.
2. **drand imzası geçerli.** Sahte bir rastgele değer, internet taklit edilse bile BLS kontrolünden geçmez.
3. **Kendi makinende yeniden koşu.** `verify.py` sinek beynini ve motoru, taahhüt + beacon'dan hesapladığı tohum ve
   kaleci yeriyle yeniden koşturur ve her sayıyı, beynin bütün spike'larının özeti dahil, birebir karşılaştırır.

Akın'ın kendi Mac'inde çekilmiş bir "DOĞRULANDI" ekranı kanıt değildir. Kanıt, **senin** kendi indirdiğin dosyalarla
kendi makinende aldığın sonuçtur.

Bilinmesi gereken: kurallar sinek ölçüldükten sonra seçildi ve bu kurallarla sinek ~%98 favori (`oyun/olasilik.py`).
Her seri adil, ama "kurallar sonuçtan bağımsız seçildi" denemez.

## Gerekenler

| | Windows 10/11 | macOS (Apple Silicon / Intel) | Linux (Ubuntu 24.04) |
|---|---|---|---|
| Python 3.12 (referans 3.12.10) | python.org'dan 3.12 kurucusu ("py launcher" ile) | `brew install python@3.12` ya da python.org | `sudo apt install python3.12 python3.12-venv python3.12-dev` |
| C/C++ derleyici (Brian2 Cython) | "Build Tools for Visual Studio 2022" → *Desktop development with C++* | `xcode-select --install` | `sudo apt install build-essential` |
| git | git-scm.com | Xcode araçlarıyla gelir | `sudo apt install git` |
| Node.js (isteğe bağlı) | nodejs.org | `brew install node` | `sudo apt install nodejs` |

Disk: ~1 GB (beyin ortamı ~530 MB, model verisi ~104 MB). İnternet: paketler, model verisi ve drand relay'leri için.
Node.js varsa `verify.py` ayrı yazılmış bir JavaScript kontrolünü de çalıştırır; yoksa o kontrolü atlar.

**Derleyici şart.** `beyin/beyin_model.py` Brian2'nin hedefini `cython` olarak sabitler. Brian2 bu durumda derleyici
bulamazsa numpy'ye **geçmez**; beyin koşusu hata verir ve doğrulama "DOĞRULANAMADI" der (sessizce geçmez; CI'da
ölçüldü). `araclar/kur.py` en sonda küçük bir derleme denemesi yapar ve eksikse ne kurulacağını söyler.

## Komutlar: kopyala, yapıştır

Her adım bir Python betiği (kabuk betiği yok). `-I`: Python'u ortam değişkenlerinden ve bulunduğu klasördeki
dosyalardan yalıtır.

### Windows (PowerShell)

```powershell
git clone https://github.com/akinaydin0/sinek-beyni-penalti.git
cd sinek-beyni-penalti
py -3.12 -I araclar\kur.py          # 1) kurulum: beyin\.venv, birebir paket sürümleri, derleme denemesi
py -3.12 -I araclar\veri_indir.py   # 2) Shiu et al. model dosyaları (~104 MB) + SHA-256 kontrolü
py -3.12 -I araclar\testler.py      # 3) dosya özetleri, duyuru özeti, 22 test
py -3.12 -I araclar\dogrula.py      # 4) PROVA5'i beyin yeniden koşusuyla doğrula
```
`py` komutu yoksa (Python'u Microsoft Store'dan kurduysan) `python` yaz ve `python --version` 3.12 göstermeli.

### macOS (Terminal)

```bash
git clone https://github.com/akinaydin0/sinek-beyni-penalti.git
cd sinek-beyni-penalti
python3.12 -I araclar/kur.py
python3.12 -I araclar/veri_indir.py
python3.12 -I araclar/testler.py
python3.12 -I araclar/dogrula.py
```

### Linux (bash)

```bash
git clone https://github.com/akinaydin0/sinek-beyni-penalti.git
cd sinek-beyni-penalti
python3.12 -I araclar/kur.py
python3.12 -I araclar/veri_indir.py
python3.12 -I araclar/testler.py
python3.12 -I araclar/dogrula.py
```

### Beklenen sonuç (PROVA5)

```
sinek beyni: 5 şutun 5'inde spike'lar Mac referansıyla BİT BİT AYNI
verify.py sonucu: PROVA DOĞRULANDI (final sonuç DEĞİL) (çıkış 3)
```
- "PROVA DOĞRULANDI", final sonucun DEĞİL tatbikatın tuttuğu anlamına gelir (çıkış kodu 3).
- 1 UYARI normal: provada taahhüt turdan yalnız 5 dakika önceydi (finalde en az 120 dk).
- Akın'ın Mac'i dışındaki makinelerde 1 UYARI daha çıkar: "beyin ortamı taahhüttekinden farklı". Sebep platform adı
  (ör. `Windows-…`); paket sürümleri aynı, yalnız Windows'ta Brian2 fazladan `py-cpuinfo` kurar. Spike'lar yine
  birebir karşılaştırılır.
- İlk koşu daha uzun sürer: Brian2 ağın kodunu bir kez derler (önbellek: Windows `%USERPROFILE%\.cython`,
  macOS `~/Library/Caches/cython`, Linux `~/.cython`; `CYTHON_CACHE_DIR` ile değiştirilebilir).

### Final günü: bir taahhüdü doğrula

`--kod`, `--duyuru-sha` ve `--yayin-utc` değerlerini **kendin** dış kaynaktan oku: TAM SHA-256 sabitlenmiş
gönderiden, duyuru özeti bir gün önceki duyurudan, zaman bu depodaki commit'in GitHub saatinden ya da OpenTimestamps
kaydından. Dosyalardan okuma; operatörün elinde olan dosyalar kanıt değildir.

```bash
python3.12 -I araclar/dogrula.py --taahhut veri/taahhut.json --config oyun/config_final.json \
    --log veri/penalty_log.json --karar veri/beyin_kararlari.json --beacon-dosya veri/beacon.json \
    --kod <TAM_64_KARAKTER_SHA256> --duyuru-sha <DUYURU_OZETI> --yayin-utc <2026-10-23T12:04:00Z>
```
Windows'ta aynı komut: `py -3.12 -I araclar\dogrula.py --taahhut veri\taahhut.json ...` (satır sonundaki `\` yerine
PowerShell'de tek satır yaz ya da satır sonuna `` ` `` koy). Beklenen son satır: `SONUÇ: DOĞRULANDI` (çıkış 0).

`araclar/dogrula.py`, `oyun/verify.py`'yi **değiştirmeden** çağırır. İstersen doğrudan da çalıştırabilirsin:
`python3.12 -I -X utf8 oyun/verify.py --help`.

## Platformlar arası sonuç (GitHub Actions)

`.github/workflows/dogrulama.yml` her değişiklikte üç işletim sisteminde aynı dört adımı çalıştırır ve sinek
beyninin spike'larının Mac referansıyla bit bit aynı olup olmadığını raporlar. Son koşular: depodaki **Actions** sekmesi.

Ölçüm (22 Ekim 2026, Python 3.12.10, aynı 25 paket; depo `sinek deneme ç` adlı boşluklu klasörde çalıştı):

| | Windows Server 2025 (x64) | macOS 26 (arm64) | Ubuntu 24.04 (x64) | Referans: Akın'ın Mac'i (M2 Pro) |
|---|---|---|---|---|
| Derleyici (Brian2 Cython) | MSVC `/Ox /arch:AVX2` | clang `-O3 -ffast-math -march=native` | gcc `-O3 -ffast-math -march=native` | clang, aynı bayraklar |
| `verify.py` sonucu | PROVA DOĞRULANDI | PROVA DOĞRULANDI | PROVA DOĞRULANDI | PROVA DOĞRULANDI |
| Sinek beyni, 5 şut | **5/5 bit bit aynı** | **5/5 bit bit aynı** | **5/5 bit bit aynı** | (referans) |
| Kontrol satırları Mac çıktısıyla | aynı | aynı | aynı | — |
| Brian2 numpy hedefiyle (derleyicisiz) | 5/5 aynı | 5/5 aynı | 5/5 aynı | 5/5 aynı |
| Süre/şut: cython · numpy | 5,0 s · 44 s | 3,0 s · 12,9 s | 4,1 s · 14,5 s | 3,0 s · 10,4 s |
| Kurulum · indirme · testler · doğrulama | 64 · 2 · 12 · 73 s | 45 · 1 · 12 · 51 s | 46 · 1 · 19 · 53 s | — |

- "Bit bit aynı": her şutta bütün spike'ların (nöron numarası + zaman) SHA-256'sı, 14 nöron grubunun sayıları,
  steer, nişan, hız ve karar süresi Mac'tekiyle aynı; raster dosyaları da aynı.
- Derleyicisiz deneme (Linux, `CC=/bin/false`): doğrulama **DOĞRULANAMADI** dedi; sessizce geçmedi.
- Türkçe 8-bit yerel ayar benzetimi (Linux, ISO-8859-9 = cp1254 gibi): düz Python ile **DOĞRULANAMADI**
  (`'utf-8' codec can't decode byte 0xfe`); `-X utf8` kalkanıyla PROVA DOĞRULANDI.
- Windows'ta Brian2 bir paket daha kurar (`py-cpuinfo==9.0.0`); `verify.py` bunu UYARI satırında gösterir.
- Sınır: bu, PROVA5'in 5 şutu ve bu CI makineleri için bir ölçümdür. Başka bir işlemci ya da derleyici sürümü
  için kanıt değildir; bu yüzden herkesin kendi makinesinde koşturması isteniyor. Tutmazsa `verify.py` HATA verir.

## Windows notları (neden bu betikler var?)

- **Türkçe karakterler:** Windows konsolu ve borular cp1252/cp1254 kullanabilir. Betikler çıktıyı UTF-8'e zorlar ve
  `verify.py`'yi `-X utf8` ile çalıştırır.
- **Beyin alt süreci:** `verify.py` beyni ayrı bir süreçte koşturur ve çıktısını UTF-8 çözer. Türkçe Windows'ta (cp1254)
  o süreç "ş" harfini tek bayt (0xFE) yazar ve çözüm patlar. `kur.py` bu yüzden `beyin\.venv\python_utf8.cmd` yazar:
  aynı Python'u `-X utf8` ile başlatır, yalnız metin kodlamasını değiştirir. `dogrula.py` Windows'ta bunu kullanır.
  (CI'da Linux üzerinde Türkçe 8-bit yerel ayarla ölçüldü: kalkansız DOĞRULANAMADI, kalkanlı PROVA DOĞRULANDI.)
- **`beyin/.venv/bin/python`:** taahhüde giren kod beyin Python'unu bu yolda arar; Windows venv'i ise
  `Scripts\python.exe` kullanır. `kur.py` `bin\` içine bir kopya koyar. Taahhüt edilmiş kod değiştirilmedi.
- **Satır sonları:** taahhüde giren dosyalar SHA-256 ile kontrol edilir. Windows git'i (core.autocrlf=true) LF'yi CRLF'ye
  çevirirse özetler tutmaz. `.gitattributes` (`* -text`) bunu kapatır; `testler.py` CRLF görürse söyler.
- **Boşluklu ve Türkçe karakterli yollar:** her yol listesiyle (kabuk olmadan) veriliyor; CI depoyu
  `sinek deneme ç` adlı bir klasörde çalıştırır.
- **Kullanıcı adında Türkçe karakter varsa** (ör. `C:\Users\Akın`) ve derleme yol yüzünden hata verirse, Brian2'nin
  derleme önbelleğini ASCII bir klasöre al: PowerShell'de `$env:CYTHON_CACHE_DIR = "C:\cython_onbellek"`.
- **python / python3.12 / py:** betikler Python 3.12 değilse durur ve doğru komutu söyler.

## Klasörler

| Yol | Ne |
|---|---|
| `oyun/` | Motor, taahhüt (`commit.py`), drand (`beacon.py`), saf Python BLS (`bls12381.py`), doğrulama (`verify.py`, `beyin_yeniden.py`), testler, bağımsız JS kontrolü (`bagimsiz/kontrol.mjs`). 11 dosya taahhüde girer. |
| `beyin/` | Sinek beyni: `kick.py`, `beyin_model.py`, `ortam.py`, `esleme.py` (DONMUŞ), `dondur.py`, `ids.json`, `DONDURMA.json` (taahhüde girer) + kalibrasyon ve kontrol betikleri. `indirilen/` boş; `veri_indir.py` doldurur. |
| `araclar/` | Kurulum ve çalıştırma kolaylığı (taahhüde girmez): `kur.py`, `veri_indir.py`, `testler.py`, `dogrula.py`; tanı aracı `beyin_hedef_olcum.py`; CI özeti `ci_ozet.py`. |
| `veri/prova5/` | PROVA5: config, taahhüt, beacon, beyin kararları, penaltı log'u ve Mac'teki verify çıktısı. |
| `_tur3/veri/beyin_raster/prova5_beyin_kararlari/` | PROVA5'in spike raster'ları (npz). Yol tuhaf ama değiştirilemez: beyin karar dosyası bu yolu içeriyor ve o dosya taahhüt zincirine bağlı. |
| `veri/ara_prova4/` | Ara prova 4 (3–2). Taahhüdü `veri/taahhut_gecmisi.jsonl`'da kayıtlı; sonra kod değiştiği için bugünkü `verify.py` ile bilerek DOĞRULANAMADI alır. "Her taahhüt yayınlanır" kuralı gereği burada. |
| `veri/duyuru.json` | Duyuru özeti (kurallar + 21 kod/veri dosyası): `572bbd8a…`. |
| `veri/kalibrasyon.json`, `pilot.json`, ... | Beyin kalibrasyonu ve gerçeklik kontrollerinin sonuçları (`beyin/README.md`). |

## Lisans ve atıflar

Bu projenin kodu MIT lisanslıdır (`LICENSE`). Shiu ve ark. modeli (MIT), FlyWire v783 verisi (CC BY 4.0), Brian2
(CeCILL 2.1) ve diğerleri bu depoda **yoktur**; indirilir ya da kurulur. Lisansları ve zorunlu atıflar:
`THIRD_PARTY_LICENSES.md`. EA'ya ait hiçbir görsel, logo ya da oyun görüntüsü kullanılmadı; Uğurcan Çakır'ın yalnız adı
ve resmi FC 27 değerleri kullanıldı. Bu proje EA, oyuncu ya da kulübüyle bağlantılı değildir.

---

<a id="english"></a>
## English

**A fruit-fly brain model takes 5 penalties. I did not pick the result; this repository lets you check that on
your own computer.**

> **Status (22 Oct 2026):** preparation. The final run has **not** happened. The only run here is **PROVA5**, a dry
> run; its score (FLY 5 – 0 ÇAKIR) is **not** the published result.

**What it is.** The Shiu et al. (Nature 2024) whole-brain leaky integrate-and-fire model of *Drosophila* (FlyWire v783
connectome, 138,639 neurons, 15.1 M connections, Brian2) sees where the goalkeeper stands (as a left/right bias on the
LC10 visual neurons), runs for 1 s, and its steering and forward-walking descending neurons are turned into an aim
point and shot speed by a readout frozen before calibration (`beyin/esleme.py`, digest `e0ff656d…`). A pure-Python
physics engine plays the keeper, "Uğurcan Çakır", with his EA SPORTS FC 27 ratings (DIV 80, HAN 76, KIC 81, POS 80,
REF 82). Honest finding: the fly turns **towards** the keeper (object tracking), it does not "read and fool" him.

**Rules (inside the commitment).** 5 kicks, every kick counts, no retries; goal = FLY, save/post/wide/over = ÇAKIR.
Realistic keeper (Hunter 2018 save probability vs. shot speed). Before each kick the keeper shifts 0.30–0.50 m to a
random side; the shifts and the brain seed come from drand quicknet round N, published **after** the commitment
(BLS12-381 signature checked by our own pure-Python `oyun/bls12381.py`). Rules + all code are announced a day before
(announcement digest); the commitment must be public at least 120 minutes before round N; every commitment made is
resolved and published.

**What verification proves.** (1) that the commitment was public before round N: *you* read that time from an
external source (GitHub commit time, pinned post, OpenTimestamps) and pass it as `--yayin-utc`; (2) that the drand
value is genuine (BLS); (3) that the brain and engine, re-run **on your machine** with the seed and keeper positions
derived from commitment + beacon, reproduce every number, including a SHA-256 over all brain spikes. A screenshot of
"DOĞRULANDI" from the operator's machine proves nothing. Caveat: the rules were chosen after the fly was measured
and under them the fly is a ~98% favourite.

**Requirements.** Python 3.12 (reference 3.12.10), a C/C++ compiler for Brian2's Cython target (Windows: Build Tools
for Visual Studio 2022, "Desktop development with C++"; macOS: `xcode-select --install`; Linux: `build-essential`,
`python3.12-dev`, `python3.12-venv`), git, ~1 GB disk; Node.js optional (independent JS check). Without a compiler
the brain run fails loudly (no silent fallback to numpy, because `beyin_model.py` pins `cython`).

**Commands.** Windows (PowerShell): `py -3.12 -I araclar\kur.py`, then `araclar\veri_indir.py`,
`araclar\testler.py`, `araclar\dogrula.py`. macOS / Linux: `python3.12 -I araclar/kur.py`, then
`araclar/veri_indir.py`, `araclar/testler.py`, `araclar/dogrula.py` (full blocks above). They (1) build `beyin/.venv`
with the exact package versions and test-compile Brian2, (2) download the Shiu et al. files from commit `91bdd1e7…` and
check SHA-256 against `beyin/ids.json`, (3) check the 21 committed files' SHA-256 and the announcement digest and run
the 22 tests, (4) run `oyun/verify.py` unchanged, with the brain re-run, on PROVA5. Expected:
`PROVA DOĞRULANDI (final sonuç DEĞİL)`, exit code 3, and "5 of 5 kicks bit-identical to the Mac reference".
Non-Mac machines show one extra warning ("brain environment differs"), caused only by the platform string.
For the final, pass `--taahhut --config --log --karar --beacon-dosya` plus `--kod`, `--duyuru-sha`, `--yayin-utc`
read from external sources; expected `SONUÇ: DOĞRULANDI`, exit 0.

**Windows pitfalls handled.** UTF-8 output forced and `verify.py` run with `-X utf8`; a `python_utf8.cmd` launcher for
the brain subprocess (otherwise Turkish code page cp1254 breaks decoding of its output, measured on Linux with a
Latin-5 locale); a copy of `Scripts\python.exe` at `beyin\.venv\bin\python` because the committed code expects that
path; `.gitattributes` `* -text` so git does not turn LF into CRLF (which would change the committed SHA-256s);
paths with spaces and non-ASCII characters (CI runs from a folder called `sinek deneme ç`). If your Windows user
name has non-ASCII characters and compilation fails, set `$env:CYTHON_CACHE_DIR = "C:\cython_cache"`.

**Cross-platform results (measured 22 Oct 2026, GitHub Actions, Python 3.12.10, same 25 packages).** On Windows
Server 2025 x64 (MSVC `/arch:AVX2`), macOS 26 arm64 (clang) and Ubuntu 24.04 x64 (gcc, `-ffast-math -march=native`)
`verify.py` gave `PROVA DOĞRULANDI` and the brain re-run was **bit-identical to the Mac reference in 5 of 5 kicks**
(SHA-256 over all spikes, all counts, aim, speed, decision time, rasters). Brian2's numpy target (no compiler) was
also identical on all three. Time per kick, cython vs numpy: Windows 5.0 s vs 44 s, macOS 3.0 s vs 12.9 s, Linux
4.1 s vs 14.5 s. Without a compiler the verification fails (`DOĞRULANAMADI`), it does not pass silently. With a
Turkish 8-bit locale (ISO-8859-9, like Windows cp1254) the brain subprocess output breaks UTF-8 decoding unless the
`-X utf8` launcher is used (measured). This is a measurement for these 5 kicks on these machines, not a proof for
every CPU/compiler, which is why everyone is asked to re-run it themselves.

**License.** Project code: MIT (`LICENSE`). Third-party code and data are not included; licenses and required
citations (Shiu et al. MIT; FlyWire v783 CC BY 4.0 with Dorkenwald 2024, Schlegel 2024, Zheng 2018, Buhmann 2021,
Heinrich 2018, Eckstein 2024; Brian2 CeCILL 2.1, Stimberg 2019) are in `THIRD_PARTY_LICENSES.md`. No EA assets are
used; not affiliated with EA, the player or his club.
