# oyun/: penaltı motoru

Sinek beyninin kararını (`aim`, `speed_mps`) alır, topu ve Uğurcan'ı fizikle oynatır,
sonucu `penalty_log.json` olarak yazar (biçim: `../SOZLESME.md`). Hiçbir sonuç elle seçilmez:
kalecinin yönü ve çıkış zamanı her şut için önceden yazılmış seed'den, şut bilinmeden çekilir.

Saf Python 3, ek paket yok. Aynı girdiler her zaman bayt bayt aynı çıktıyı verir.
[tur3b 2026-10-22] Kaleci dalışı balistik (itme, yerçekimiyle uçuş, iniş, kayma; `MODEL.md` bölüm 2) ve isteğe bağlı
şut sapması (seçenek B, `config_sablon.json` → `sut_sapmasi.acik`, varsayılan KAPALI; `MODEL.md` bölüm 8).
B'nin hazır şablonu (proje kökünden): `_tur3/oyun_B/config_sablon.json` (tek fark `acik: true` ve not satırı).
Formüller ve kaynaklar: `MODEL.md`. Kaynak listesi: `LISANSLAR.md`.

## Dosyalar
| Dosya | Ne işe yarar |
|---|---|
| `penalty_model.py` | Motor: top (yerçekimi + hava sürtünmesi, RK4 600 Hz → 60 fps), direkler, kaleci, Türkçe açıklama cümlesi |
| `config_prova.json` | ESKİ PROVA ayarı (Hunter kapalı, merkeze çekilme 0,005): eski prova dosyaları bununla doğrulanır |
| `config_sablon.json` | [tur3 2026-10-22] YENİ şablon: Hunter açık, merkeze çekilme 0, kayma kuralı (`keeper_shift`), drand beacon bloğu, skor kuralı |
| `commit.py` | Taahhüt: TAM SHA-256; `kurallar` = DUYURU ÖZETİ (kurallar + kod); `yeni` config + gelecekteki drand turu + kod özetleri; `hesapla` taahhüt [tur3] |
| `beacon.py` | [tur3] drand quicknet (sabit zincir bilgisi): tur saati, relay'lerden çekme, BLS + SHA-256 kontrolü, 5 kayma, beacon'dan beyin tohumu |
| `verify.py` | [tur3] Her şeyi baştan kontrol eder: taahhüt, kurallar, kod özetleri, BLS, relay'ler, dış zaman, beyin YENİDEN KOŞUSU, motor; ilk satır MOD; sonuç etiketleri `_tur3/YENI_AKIS.md`'de |
| `bls12381.py` | [tur3] Bağımlılıksız saf Python BLS12-381 imza doğrulayıcı (RFC 9380 hash_to_curve, eşleştirme); drand quicknet için |
| `beyin_yeniden.py` | [tur3] verify.py'nin beyin yeniden koşusu (beynin kendi venv'iyle, dosya yazmaz) |
| `bagimsiz/kontrol.mjs` | [tur3] Bağımsız JavaScript uygulaması: kaymalar, beyin tohumu, kaleci seed'leri (yalnız Node crypto) |
| `tests.py` | 29 test (11 motor + 11 tur3 + 7 tur3b; düz betik, pytest gerekmez, ağa çıkmaz) |
| `olasilik.py` | [tur3] TAHMİN: beynin gerçek nişan dağılımı + yeni motorla 20.000 seri Monte Carlo (sonuç DEĞİL); [tur3b] `--sapma kapali|acik` = seçenek A/B |
| `kalibrasyon.py` | Modeli gerçek penaltı istatistikleriyle (Bar-Eli 2007, Hunter 2018) kıyaslar; sonuç: `kalibrasyon_sonuc.txt`; [tur3b] `--sapma-kalibre`: şut sapması ölçeğini gerçek kaçan oranına (Vollmer 2024) kalibre eder |
| `stub/stub_beyin_kararlari.json` | SAHTE karar dosyası (Godot/Blender geliştirmesi için) |

## Çalıştırma
```bash
cd "sinek-penalti/oyun"
python3.12 -I tests.py                     # 29/29
python3.12 -I penalty_model.py --karar stub/stub_beyin_kararlari.json --config config_prova.json \
    --taahhut ../veri/taahhut_prova.json --cikti ../veri/ornek_penalty_log.json
python3.12 -I kalibrasyon.py
```
Üretilmiş prova dosyaları (hepsi PROVA, yayımlanacak sonuç değil):
- `../veri/ornek_penalty_log.json`: stub kararlarla 5 şut (gol, kurtarış, ıska var), `"stub": true`
- `../veri/prova_penalty_log.json`: beyin parçasının `prova_beyin_kararlari.json` dosyasıyla deneme koşusu
- `../veri/taahhut_prova.json`: prova taahhüdü (story'de PAYLAŞILMAZ)

## Final akışı (tur3b, 22 Ekim; sıra önemli)
Aşağısı plan. [tur5 2026-11-02] Gerçekte: G-1 adımı yapılmadı (duyuru özeti taahhütle aynı yorumda açıklandı), taahhüt
drand turundan önce yalnız Bölüm 1 reel'inin altındaki Instagram yorumunda açıktı, depo koşudan sonra açıldı.
```bash
python3.12 -I commit.py kurallar --yaz ../veri/duyuru.json                       # G-1) DUYURU ÖZETİ: herkese açık
python3.12 -I commit.py yeni --cikti config_final.json                           # 1) config, drand turu N (180 dk sonra)
python3.12 -I commit.py hesapla --config config_final.json --yaz ../veri/taahhut.json   # 2) TAM SHA-256 -> HEMEN herkese açık yere
python3.12 -I beacon.py getir --config config_final.json --yaz ../veri/beacon.json --bekle             # 3) N yayınlanınca
python3.12 -I beacon.py kaymalar --config config_final.json --taahhut ../veri/taahhut.json --beacon-dosya ../veri/beacon.json  # 4)
# 5) beyin: 4. adımın bastığı kick.py komutu (beyin/ klasöründen, --final; tohum beacon'dan)
python3.12 -I penalty_model.py --karar ../veri/beyin_kararlari.json --config config_final.json \
    --taahhut ../veri/taahhut.json --beacon <randomness> --cikti ../veri/penalty_log.json                         # 6)
python3.12 -I verify.py --taahhut ../veri/taahhut.json --config config_final.json --log ../veri/penalty_log.json \
    --karar ../veri/beyin_kararlari.json --beacon-dosya ../veri/beacon.json \
    --kod <TAM SHA-256> --duyuru-sha <duyuru özeti> --yayin-utc <açık yerde ilk görülme, UTC>                    # 7)
```
`verify.py` "SONUÇ: DOĞRULANDI" demeden Godot/Blender'a geçilmez. Bu sonuç yalnız onu kendi makinesinde çalıştıran için
kanıttır. Taahhütten sonra kodda ya da config'te tek bayt değişirse doğrulama bilerek bozulur.

### Eski taahhütler
[tur3 2026-10-22] Eski provalar (`../veri/taahhut_prova.json`, `_tur3/veri/taahhut_prova3.json`) yeni `verify.py` ile
DOĞRULANAMADI alır: taahhütlerinde kod özetleri, sabit drand bilgisi ve beacon'dan beyin tohumu yok. Bu beklenen bir şey;
o dosyalar eski `verify.py` ile (`oyun/` takastan önceki hâli, `_tur3/_kurcalama/temiz/oyun`) doğrulanır.

## [tur4 2026-10-23] Motor 1.1.1: direkten gol
Direğe ya da üst direğe çarpan şutun sonucu artık kale çizgisinde verilir (IFAB Kural 10): top sonra çizgiyi çerçevenin
içinden geçerse **GOL** (`outcome: goal`, `event.type` direk/üst direk, `event.direkten_gol: true`, `event.cizgi`), geçmezse
**DİREK** (`outcome: post`, `direkten_gol: false`). Aynı hata şut sapması kalibrasyonunu da etkilemişti: ölçek 0,332 → **0,432**
(kaçan oranı yine %4,78; `kalibrasyon_sonuc.txt`). 1.1.0'da direkten ağlara giden top da "post" yazılıyordu (ekranda filede
top + DİREK etiketi). Çelme kuralı aynı. Ayrıntı: MODEL.md bölüm 1 ve 5; ölçüm `../_tur3/tur3b_olcum/direk_olcum_*`.

## Dürüst sınırlar
- [tur3b 2026-10-22] Balistik kaleciyle isabetli şutlarda Bar-Eli ağırlıklı kurtarış %15,4 (gerçek %14,7; eski yol %17,4),
  hiçbir sabit uyum için değiştirilmeden. Kalkış açısı, gövde eğimi, iniş kaybı ve kayma sürtünmesi varsayım.
- [tur3b] Şut sapması (B) laboratuvar verisinin (Hunter 2018) biçimini kullanır, büyüklüğü maç verisine (%4,78 kaçan)
  kalibre edilmiştir; modelde kaçanların çoğu direk (gerçekte direk/aut oranı daha dengeli olabilir, MODEL.md bölüm 8).
- [tur3 2026-10-22] Aşağıdaki iki madde tur3 şablonunda ÇÖZÜLDÜ: Hunter modeli açık (isabetli şutlarda Bar-Eli
  ağırlıklı kurtarış %17,4) ve kalecinin yeri beyin ile motorda aynı (merkeze çekilme 0). Sonuç: **Positioning 80
  artık motorda hiçbir sayıyı değiştirmiyor.** BLS imzası `bls12381.py` ile kontrol ediliyor (bkz. `../_tur3/YENI_AKIS.md`).
- **Kaleci gerçekte olduğundan iyi (eski prova ayarı).** Varsayılan kural (brief'teki gibi "el ya da gövde topa yetişirse kurtarış")
  isabetli şutların %25,8'ini kurtarıyor; gerçekte bu oran %14,7-16,5. Doğru tarafa atlayınca kurtarış
  modelde ~%50, gerçekte ~%27. Sebep: kaleci 0,248 s'den sonra topun nereye gideceğini kusursuz biliyor ve topu
  hiç kaçırmıyor. Hunter'ın (2018) yayımlanmış "menzil içindeki topu durdurma olasılığı" açılırsa
  (`keeper_model.in_reach_save_model = {"a": -0.0447, "b": 1.72}`) genel oran %17,4'e iner. Bu seçenek
  brief kuralını değiştirdiği için kapalı bırakıldı; **karar taahhütten önce verilmeli.**
- FC reytinglerini fiziğe çeviren yayımlanmış bir formül yok. Eğimler bizim varsayımımız; temel değerler kaynaklı.
- Top dönmüyor (falso/Magnus yok), Cd sabit 0,25. Kaleci tek bir düzlemde (z = 0,20 m) üç kapsül olarak modelleniyor.
- Kurtarılan topun sekişi ve file basit; yalnızca görüntü içindir, sonucu etkilemez.
- Sahnede `keeper_x` 0 ise Positioning hiçbir şeyi değiştirmez (tur3'te hiç değiştirmez). Kicking hiçbir şeyi değiştirmez.
- Seed'lerin önceden "beğenilerek" seçilmediğini taahhüt tek başına kanıtlamaz. [tur3 2026-10-22] Tur3b akışında:
  drand turu N taahhütten sonra yayınlanır; kaleci seed'leri, kaymalar ve beyin tohumu ondan çıkar; kuralların ve kodun
  özeti taahhütle birlikte açıklanır. Kalan şart: taahhüdün N'den önce herkese açık olduğunu doğrulayan kişinin dış bir
  kaynaktan ([tur5 2026-11-02] bu koşuda Bölüm 1 reel'inin altındaki Instagram yorumunun saati) kendisinin kontrol
  etmesi; program bunu yapamaz.
