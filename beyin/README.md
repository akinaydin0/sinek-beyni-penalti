# beyin/ — sinek beyni penaltı kararı veriyor

## Bu ne?

Yayımlanmış gerçek bir modelin bu Mac'te çalışan kopyası: Shiu et al. (Nature 2024) meyve sineği tüm-beyin modeli.
Model 138.639 nöron ve 15,1 milyon bağlantıdan oluşuyor; bağlantılar FlyWire v783 beyin haritasından geliyor.

Penaltı için şöyle kullanıyoruz:

1. Kalecinin yeri sineğin görme nöronlarına (LC10, iki gözde 816 nöron) uyarı olarak verilir. Kaleci hangi taraftaysa o taraftaki gözün nöronları daha sık uyarılır.
2. Beyin 1 saniye çalışır.
3. Yürürken sağa ya da sola döndüren 10 inen nöron (DNa01, DNa02, DNb05, DNg13, DNb06, sağ ve sol) ile ileri iten 2 nöron (oDN1) sayılır.
4. Bu sayılar, önceden yazılıp dondurulmuş bir formülle nişan noktasına (x, y) ve top hızına çevrilir (`esleme.py`).

Elle seçilen hiçbir şey yok. Her deneme bir tohum (seed) ile kayda geçer ve aynı tohum birebir aynı spike'ları verir.

## Ne bulduk (düz dille)

- **Gerçek beyin kontrolü geçti.** Şeker tadı nöronları uyarılınca ağzı açan motor nöron (MN9) saniyede 67 kez ateşledi. Makalenin kendi deposundaki sonuç da 67. Uyarı verilmeyince MN9 hiç ateşlemedi. (`../veri/smoke_test_seker_mn9.json`)
- **Hızlı sürüm orijinalle aynı sonucu veriyor:** 100 Hz'de 67,6, 200 Hz'de 92,5. Depodaki karşılıkları 67,0 ve 93,3. (`../veri/capraz_kontrol.json`)
- **Sinek kalecinin tarafına göre yön değiştiriyor.** Kaleci soldayken 30 denemenin 30'unda sola döndü, sağdayken 30'unda sağa. Ama kaleciden kaçmıyor, ona *doğru* dönüyor, yani bir nesneyi takip eden sinek gibi davranıyor. Penaltıda bu, şutu kalecinin olduğu tarafa atmak demek. Kaleci 1,83 m'deyken nişan x yaklaşık ±3,0–3,2 m çıkıyor: kalecinin tarafı ama direğe yakın.
- **Kaleci tam ortadayken bile 30 denemenin 30'unda sola döndü** (ortalama steer −0,58). Bunu biz ayarlamadık. Kaynağı beyin haritasındaki sol-sağ bağlantı farkı: iki taraf aynı uyarıyı alınca sol DNa02 daha kolay ateşleniyor. Nöron sayısı bunu açıklamıyor, çünkü sağ gözde LC10 nöronu daha fazla (sağda 413, solda 403).
- **Prova 5 şut** (kaleci ortada, tohum 7000001–7000005): beşi de sola gitti. Nişan x: −1,51 ile −2,35 m arası, yükseklik 1,52–1,65 m, hız 26,3–27,2 m/s.
- **Süre:** 1 s'lik beyin denemesi yaklaşık 2,8–3 s sürüyor; ağın kurulması ~1–3 s. Orijinal kod deneme başına ~43 s.

## Nasıl çalıştırılır

```bash
cd "sinek-penalti/beyin"
.venv/bin/python -I smoke_test.py          # şeker → MN9, orijinal Shiu kodu (~15 dk)
.venv/bin/python -I capraz_kontrol.py      # hızlı sürüm = orijinal mi? (~3 dk)
.venv/bin/python -I kimlikler.py           # ids.json (DONDURULDU; yeniden üretilirse özet değişir)
.venv/bin/python -I dogrula_v783.py        # tüm kimlikler resmi v783 listesinde mi?
.venv/bin/python -I dondur.py --kontrol    # esleme.py + ids.json donmuş özetle aynı mı?
.venv/bin/python -I kalibrasyon.py         # 3 sahne x 30 deneme (~5 dk) → veri/kalibrasyon.json, cikti/kalibrasyon.png
.venv/bin/python -I kick.py --n 5 --seed-base 7000000 --keeper-x 0.0 \
    --out "../veri/prova_beyin_kararlari.json"                    # PROVA
.venv/bin/python -I raster.py --npz ../veri/beyin_raster/prova_beyin_kararlari/kick_01.npz \
    --out ../cikti/raster_prova_kick_01.mp4                       # 1080x1920, 60 fps, 5 s
```

**Final koşu yalnızca story'deki taahhütten sonra yapılır:**

```bash
.venv/bin/python -I kick.py --final --n 5 --seed-base <S> --keeper-x <X> \
    --commit-sha256 <story'deki özet> --out ../veri/beyin_kararlari.json
```

`kick.py` dört durumda çalışmayı reddeder:
- `esleme.py` ya da `ids.json` donmuş özetle uyuşmuyorsa,
- kalibrasyon başka bir okumayla yapılmışsa,
- `--final` verilmeden prova olmayan bir dosyaya yazılmak isteniyorsa,
- final dosya zaten varsa (yeniden deneme yok).

`--keeper-x` tek bir değer ya da şut başına virgüllü bir liste olabilir (eksiyle başlıyorsa `--keeper-x=-0.3,0,...` yaz).

**Doğrulama:** `cat esleme.py ids.json | shasum -a 256` komutu
`e0ff656deddd74430262a8b5b272ca9842ae75a2f9b8a806562cc4e42cdcaa27` vermeli.
Dondurma zamanı 2026-10-22 05:19 UTC; bu, kalibrasyondan önce. Kayıt `DONDURMA.json` dosyasında.

## Dosyalar

| Dosya | Ne yapar |
|---|---|
| `ortam.py` | Yollar ve derleyici düzeltmesi. Homebrew Python'u olmayan bir SDK'yı gösteriyordu, Xcode'un SDK'sı veriliyor. |
| `beyin_model.py` | Shiu modelinin hızlı sarmalayıcısı: aynı denklemler ve sabitler, ağ bir kez kurulur, her deneme sıfırdan başlar |
| `smoke_test.py`, `capraz_kontrol.py`, `dogrula_v783.py` | Gerçeklik kontrolleri |
| `kimlikler.py` → `ids.json` | Kullanılan bütün nöronların v783 kimlikleri ve kaynakları |
| `pilot.py` | Yön-kör pilot (yalnızca kaleci ortada, yalnızca toplam spike'lar). LC10 hızını (10 Hz), P9'un gerekmediğini ve hız/yükseklik ölçeğini (16 spike) önceden yazılmış bir kuralla seçti. |
| `esleme.py` | DONMUŞ sahne → girdi, okuma ve eşleme formülleri, her sabitin açıklaması |
| `dondur.py`, `DONDURMA.json` | Dondurma özeti ve zamanı |
| `kalibrasyon.py`, `kick.py`, `raster.py` | Kalibrasyon, şutlar, B-roll raster videosu |
| `indirilen/` | İndirilen kod ve veri (dokunulmadı). Kaynaklar `LISANSLAR.md` dosyasında. |
| `kod_test/` | Geliştirme denemeleri: derleyici testi, orijinal kodla tek deneme süresi, hız ve determinizm testi, LC10 → inen nöron bağlantı yolu analizi (`yol.py`, beyin/ içinden çalıştırılır) |
| `sonuclar/` | Duman testinin ham spike dosyaları (parquet) ve koşu kayıtları |

## Dürüst sınırlar

- **Bu yalnızca beyin.** Bacak, kas, omurilik (VNC) ya da vücut yok. "Karar", inen nöronların 1 saniyedeki spike sayısıdır; gerisi bizim sabit formülümüz.
- **Görsel sahne çok kaba.** Kalecinin yeri, sol ve sağ LC10 nöronlarına verilen uyarı hızına çevriliyor. Gerçek bir görüntü, göz haritası, hareket ya da top yok.
- **Sinek kaleciye doğru dönüyor.** Bu bir hata değil, modelin verdiği sonuç. Şutu kalecinin tarafına attırıyor.
- **Kaleci ortadaysa şutlar hep sola ve birbirine çok benzer** (steer −0,23 ile −0,80 arası). Tek değişkenlik kaynağı rastgele uyarı gürültüsü. Daha çeşitli şut isteniyorsa kalecinin konumu şut başına (tohumdan) değişmeli; bu karar oyun tarafının.
- **Hız ve yükseklik aynı sayıdan (oDN1) geliyor.** Bu yüzden birlikte artıp azalıyorlar.
- **Nöron rolleri literatürden.** Yang et al. 2024'te yalnızca DNa02 ve DNg13 doğrudan test edilmiş; DNa01, DNb05 ve DNb06'nın rolü ilişkiye dayanıyor. DNb06 bu girişle neredeyse hiç ateşlenmedi.
- **oDN1 = DNg97 eşleşmesi Sapkal et al. 2024'ten.** FlyWire açıklamalarında "oDN1" adı geçmiyor.
- **"DNa01" adı belirsiz.** FlyWire'ın DNa01'i hemibrain'de VES006 diye geçiyor. Biz FlyWire adını kullandık (ayrıntı: `ids.json` → `naming_notes`).
- **Bazı sabitler pilottan geldi.** LC10 hızı ve power ölçeği yön-kör pilottan, kalibrasyondan önce seçildi. Yine de başka değerler başka sonuç verebilir: 5 Hz'de dönüş nöronları neredeyse susuyor, 40 Hz'de çok daha güçlü ateşleniyor (`../veri/pilot.json`).
- **Spike'lar orijinal kodla birebir aynı değil.** Brian2 2.10.1 kullanıldı (makalede 2.5.1). Hızlı sürüm Poisson girdisini farklı bir rastgele sayı yolundan üretiyor; ortalamalar orijinalle aynı (çapraz kontrol), ama tek tek spike'lar değil.
- `indirilen/eon_fly_brain` yalnızca okundu ve çalıştırılmadı (GPL-2.0, 365 MB). Gerekmiyorsa silinebilir.
