# Penaltı motoru: formüller, sabitler, kaynaklar

Bütün sayılar `config_*.json` içinde durur ve taahhüt özetine girer. Kod (`penalty_model.py`) yalnızca algoritmadır.
Koordinatlar `SOZLESME.md` ile aynı: x+ şutörün sağı (= kalecinin SOLU), y yukarı, z kaleden penaltı noktasına.
Kaleci için "left/right" her yerde **kalecinin kendi** solu/sağıdır (Bar-Eli 2007 ile aynı).

> [tur3b 2026-10-22] Bu sürümde iki şey değişti (taahhütten ÖNCE kararlaştırıldı): **kaleci dalışı artık balistik**
> (bölüm 2: itme, yerçekimiyle uçuş, iniş, kayma; eski "yana uçup havada durup dikine düşen" yol kaldırıldı) ve
> **isteğe bağlı şut sapması** (bölüm 8, seçenek B; `config_sablon.json`'da varsayılan KAPALI). Motor sürümü 1.1.0.

## 1. Top
| Ne | Değer / formül | Kaynak |
|---|---|---|
| Kütle, yarıçap | 0,43 kg, 0,11 m | IFAB Kural 2, sözleşme |
| Hava, sürtünme | ρ = 1,2 kg/m³, Cd = 0,25 sabit, A = πr² | brief; süperkritik futbol topu ölçümleriyle uyumlu (Goff & Carré 2009) |
| Hareket denklemi | **a = g − k·\|v\|·v**, k = ½ρCdA/m = 0,01326 1/m | klasik ikinci dereceden sürtünme |
| Entegrasyon | RK4, 600 Hz; `trajectory` her 10 adımda bir (60 fps) `[t, x, y, z]` | brief |
| Hedef | `aim` = topun **merkezinin** kale çizgisi düzlemini (z = 0) kestiği nokta. Fırlatma yönü sabit nokta iterasyonuyla bulunur (sürtünme hıza ters olduğu için yatay yol düz çizgidir: x kesin tutar, y düşüşü iterasyonla telafi edilir). `aim.y < 0,11` ise 0,11 alınır. | |
| Uçuş süresi | `flight_time_s` = kalecisiz, direksiz serbest uçuşta z = 0'a varış. 24 m/s: orta ≈ 0,50 s, köşe 0,52-0,54 s | |
| Zemin | sekme katsayısı 0,6, teğet hız ×0,85, dikey hız 0,4 m/s altına inince yuvarlanma, yuvarlanma yavaşlaması 0,6 m/s² | varsayım (yalnız görüntü) |
| Kale | iç kenarlar x = ±3,66, üst direk alt kenarı 2,44 m, direk kalınlığı 12 cm → direk ekseni x = ±3,72, üst direk ekseni y = 2,50, eksenler z = 0, yarıçap 0,06 | IFAB Kural 1 |
| Direk teması | top merkezi ile direk ekseni arası < 0,17 m → ahşap vuruşu (üst direk dahil). Sekme: dik bileşen ×0,6, teğet ×0,9. [tur4 2026-10-23] Sonucu vuruş değil **kale çizgisi** belirler (IFAB Kural 10): top sonra çizgiyi çerçevenin içinden geçerse `goal` (direkten gol), dışından geçerse ya da hiç geçmezse `post` | brief kuralı; katsayılar varsayım; Kural 10 |
| Gol / ıska | kaleci ve direk teması yoksa, z = 0'da merkez içerideyse `goal`; dışarıdaysa `wide` ya da `over` (hangi yönde daha çok taşıyorsa) | |
| File | 1,5 m derin kutu, çok düşük sekme | yalnız görüntü |

## 2. Kaleci (Uğurcan Çakır: Diving 80, Handling 76, Kicking 81, Positioning 80, Reflexes 82, boy H = 1,91 m)
FC reytingleri oyun değerleridir, laboratuvar ölçümü değildir. **Reytingi fiziğe çeviren yayımlanmış bir formül yok**;
aşağıdaki eğimler bizim varsayımımız, dayandıkları temel değerler kaynaklıdır.

| Ne | Formül | Uğurcan | Kaynak |
|---|---|---|---|
| Tepki süresi (Reflexes) | RT = 255 − 0,4·(Reflexes − 65) ms | **0,248 s** | Piechota & Majorczyk 2023: kıdemli kaleciler 250-260 ms. Referans 65 ve 0,4 ms/puan varsayım |
| Kalkış hızı (Diving) | [tur3b] **kalkış anındaki YATAY ağırlık merkezi (COM) hızı** v = 4,0·(1 + 0,01·(Diving − 75)) m/s; uçuşta sabit kalır | **4,2 m/s** | Hunter 2018 dalış modelinde 4 m/s; Ibrahim ve ark. 2019 (10 elit kaleci, kuvvet platformu): iki bacağın yatay COM hızına katkısı 2,7 + 1,2 ≈ 3,9 m/s. Puan eğimi varsayım |
| İtme evresi | 0,40 s: yana sabit ivme (a = v/0,40, kalkışta yatay hız v); dikeyde önce çökme (countermovement) sonra kalkış (kübik eğri) | itmede COM ~0,84 m yana gider | varsayım; van der Kamp ve ark. 2018: yana dalış en az ~600 ms. Ibrahim ve ark. 2019 (Frontiers): yüksek dalışta iki itme ayağının tepe kuvvetleri arasında COM ~0,6-0,7 m yana gidiyor, çökme 8-14 cm; ışıktan topa toplam dalış süresi 0,97-1,05 s |
| ~~Ağırlık merkezi en uzun yol~~ | [tur3b] **kaldırıldı** (eski `travel_frac_*`, 1,55 m'de duruyordu). Yol artık kalkış hızı, yerçekimi ve yerle belirleniyor | | |
| Gövde oranları | COM yüksekliği 0,52H; COM→ayak 0,52H; COM→omuz 0,27H; kol 0,44H; [tur3b] COM→parmak ucu (bilek uzamış) 0,60H | | Drillis & Contini 1966; parmak ucu payı 0,08H varsayım |
| Erişim (log'daki `reach_m`) | [tur3b] artık bir sınır DEĞİL: kör dalışta (çıkış ortalama −0,19 s), top kaleye varırken (t = 0,50 s) parmak ucunun yandaki uzaklığı | **3,33 m** (eski 2,90 m sabitti) | modelden hesaplanır |
| Konumlanma (Positioning) | x_başlangıç = keeper_x·(1 − k·Positioning); eski prova k = 0,005, **tur3 şablonunda k = 0** | eski: ofsetin %40'ını kapatır; **tur3: x_başlangıç = keeper_x** | varsayım: iyi konumlanma = açıyı ortalamak. [tur3 2026-10-22] Kaleci artık bilerek 30-50 cm kayık duruyor (bölüm 7); bu duruş zaten onun yeri olduğu için çekme kapatıldı, yoksa beyin X'i, motor 0,6·X'i görürdü. **Positioning 80 tur3'te motorda hiçbir sayıyı değiştirmiyor** (Kicking gibi) |
| Tutma (Handling) | p_tut = Handling/100 · kırp((32 − v)/(32 − 15)) · kırp(derinlik / 0,20 m) | 24 m/s, derin temas: 0,36 | varsayım |
| Kicking | **etkisiz** | | penaltıda kalecinin vuruşu yoktur |

### Seed'den, şut bilinmeden çekilenler
Her şutun kendi seed'i vardır (`config.keeper_seeds[n-1]`). Rastgele sayı: **u = (SHA-256("seed|kickN|etiket") ilk 56 bit + 0,5) / 2⁵⁶**.
Python'a özgü değildir; herkes tarayıcıda bile yeniden hesaplayabilir. Normal dağılım için ters CDF kullanılır.
- **Yön**: u < 0,493 → `left`; < 0,556 → `stay`; değilse `right` (sol %49,3 / orta %6,3 / sağ %44,4, Bar-Eli ve ark. 2007, 286 penaltı, kalecinin bakışıyla).
- **Çıkış zamanı**: N(−0,19 s; 0,145 s), [−0,76; 0,30] aralığına kırpılır (Hunter 2018, 1278 penaltı; ortalama −0,19 s ayrıca Hunter ve ark. 2022).
- **Tutma zarı** (`catch`) ve isteğe bağlı model için **durdurma zarı** (`keep_out`).
`draw_plan(cfg, seed, n)` fonksiyonunun girdisinde şut yoktur; test bunu da kontrol eder.

### Hareket ([tur3b 2026-10-22] balistik dalış, `keeper_model.ucus`, sürüm `balistik-v1`)
Eski yol (inceleme: "süpermen gibi asılı kalıyor"): COM ~0,85 s yatayda 4,2 m/s ile uçuyor, 1,55 m'de **havada aniden
duruyor**, sonra **dikine** düşüyordu; ayaklar COM yüksekliğinde, gövde tam yatay. Yeni yol fiziksel olarak tutarlı:
- **Atlayan kaleci** `leave_time_s` anında, seed'in seçtiği tarafa harekete başlar. Dalış açısı φ: kör dalışta 10°
  (topu görmeden). İtme bitene (leave + 0,40 s) kadar topu görebildiyse yalnızca **yüksekliği** topa göre seçer
  (φ = COM'dan topun geçeceği noktaya açı, −35°…+45°); **tarafı asla değiştiremez**.
- **1) İtme (0,40 s, ayaklar yerde):** yana sabit ivme, kalkışta yatay hız v = 4,2 m/s, COM 0,84 m yana. İç taraftaki
  ayak önce yana adım atar (0,05 m kalkar), sonra itme ayağı **yerde sabit** kalır. Dikey kalkış hızı
  v_y = v·tan φ; sınırlar: (a) tepe noktası ayaktaki COM'un en çok 0,45 m üstü (`jump_cap_m`), (b) çökme serbest düşmeden
  hızlı olamaz (kübik eğrinin başındaki ivme ≥ −g). Kalkıştaki COM yüksekliği en çok 0,60H·sin 65° = 1,04 m (itme bacağı
  yatayla 65°, `leg_angle_takeoff_deg`); aşağı dalışta COM itme sırasında alçalır (v_y < 0). Gövde dikten 40° yana
  eğilerek kalkar (`torso_lean_takeoff_deg`).
- **2) Uçuş (mermi):** x = x_kalkış + v·t, y = y_kalkış + v_y·t − ½·g·t² (hava direnci yok). **Yatay hız uçuş boyunca
  sabit**, havada durmak yok. Gövde ve bacaklar inişe kadar yataya döner; ayaklar gövdenin altında, geride kalır.
- **3) İniş ve kayma:** COM yatma yüksekliğine (0,15 m) inince yere değer; çarpmada yatay hızın yarısı kalır
  (`landing_keep_h` 0,5), sonra sürtünmeyle (μ = 0,5, yavaşlama μg) kayıp durur: kayma 0,45 m. Sonra hareketsiz yatar.
- Örnek (kör dalış, çıkış −0,19 s): kalkış 0,21 s, tepe COM 1,07 m, iniş 0,72 s, duruş 1,15 s; COM'un yana yolu
  inişte 2,97 m, duruşta 3,42 m.
- **Ortada kalan kaleci** (`stay`) topu RT anında görür. Topa yetişmek için COM'un yana gitmesi gereken yol
  (mesafe − kol erişiminin %90'ı) ≥ 0,8 m ise RT'de **tepkiyle dalar** (aynı balistik dalış, yükseklik topa göre);
  değilse **adım atar**: COM minimum-sarsıntı eğrisiyle (en az 0,25 s) yerine gider ve yumuşak durur, ayaklar yerde;
  alçak topta en çok 0,50 m'ye çöker, yüksek topta zıplar (itme 0,40 s, çökme yine serbest düşmeden hızlı değil: en çok
  ~0,19 m), sonra ayaklarının üstüne iner. Bu durumda `leave_time_s` = RT.
- **Eller**: RT'den önce dalışla birlikte gövde doğrultusunda uzanır. RT'den sonra el, topun kaleci düzlemini keseceği
  noktaya doğru gövdeye göre en çok 4 m/s hızla gider; kol boyunu aşamaz (varsayım). [tur3b] Top kaleci düzlemini
  geçtikten 0,15 s sonra eller gövdeye döner (ayaktaysa göğüs önü, yattıysa başın önünde yerde); tutulan top eli izler
  ama yerin altına inmez. Eski "yerde yatarken topu dik kolla havada tutma" pozu böylece kalktı. Bu dönüş temas
  anından sonra olduğu için sonucu değiştirmez.
- **Temas**: kaleci düzleminde (z = 0,20 m) top merkezi ile üç kapsül arasındaki en kısa mesafe hesaplanır:
  bacaklar (ayak→COM, r = 0,10), gövde (COM→omuz, r = 0,16), kol ve eller (omuz→el, r = 0,08).
  **boşluk = mesafe − r_parça − 0,11 m**. boşluk ≤ 0 → kurtarış (brief kuralı).
- **Tür**: kol ucunda ve derinlik < 6 cm → `fingertip`; bacak → `parry`; değilse Handling zarı: u < p_tut → `catch`, değilse `parry`.
  Çelinen top kaleye girmez (kaleci düzlemi çizgiden 20 cm önde olduğu için top dışarı itilir).
- **margin_cm**: gol ve direkte kalecinin kaç cm yetişemediği; kurtarışta topun ne kadar içeriden karşılandığı;
  `wide`/`over`'da topun çerçevenin kaç cm dışından geçtiği. (`keeper_gap_cm` her durumda kalecinin boşluğudur; eksi = temas.)
- **explain**: bu sayılardan kurulan tek Türkçe cümle (`explain_tr`).

## 3. Kalibrasyon (yalnız PROVA kontrolü, `kalibrasyon_sonuc.txt`; [tur3b] yeni ölçüm `../tur3b_olcum/`)
Kale üçe bölünür; bölge içinde x düzgün, yükseklik alçağa yatık (penaltıların çoğu alt yarıya gider, Opta/Guardian 2023),
hız N(23,5; 1,9) m/s. Yalnız isabetli şutlar sayılır (Bar-Eli gibi).

| Vuruş / kaleci (kalecinin bakışıyla) | Gerçek (Bar-Eli 2007) | Model, varsayılan (temas = kurtarış) | Model, Hunter seçeneği açık |
|---|---|---|---|
| Doğru tarafa atlayış (sol/sol, sağ/sağ) | %29,6 / %25,4 | %51,5 / %49,5 | %36,0 / %35,0 |
| Ters tarafa atlayış | %0 | %0 | %0 |
| Ortaya vuruş, kaleci atlıyor (sol / sağ) | %9,8 / %3,2 | %15,0 / %18,0 | %8,5 / %9,5 |
| Ortaya vuruş, kaleci ortada (gerçekte yalnız 10 şut) | %60 | %50,5 | %32,5 |
| Yana vuruş, kaleci ortada | %0 | %0-0,5 | %0-0,5 |
| **Genel (Bar-Eli ağırlıklı)** | **%14,7** (Hunter 2018: %16,5) | **%25,8** | **%17,4** |

Hücre başına 200 isabetli şut. Kurtarış haritası (24 m/s, her yükseklik ve genişlikte) aynı dosyada.

### [tur3b 2026-10-22] Balistik kaleciyle yeniden ölçüm (`kalibrasyon.py --config config_sablon.json --n 200`, Hunter açık)
**Hiçbir sabit uyum için değiştirilmedi.** Yeni uçuş sabitleri (65°, 40°, 0,08H, 0,5, μ 0,5, 0,25 s, 0,50 m, 0,15 s)
ilk kalibrasyon koşusundan ÖNCE yazıldı; kalkış hızı, tepki, itme süresi, sıçrama sınırı eskisiyle aynı.

| Vuruş / kaleci | Gerçek (Bar-Eli 2007) | ÖNCE (eski yol, Hunter açık) | SONRA (balistik, Hunter açık) |
|---|---|---|---|
| Doğru tarafa atlayış (sol/sol, sağ/sağ) | %29,6 / %25,4 | %36,0 / %35,0 | **%30,5 / %33,5** |
| Ters tarafa atlayış | %0 | %0 / %0 | **%0 / %0** |
| Ortaya vuruş, kaleci atlıyor (sol / sağ) | %9,8 / %3,2 | %8,5 / %9,5 | %6,0 / %6,5 |
| Ortaya vuruş, kaleci ortada (gerçekte 10 şut) | %60 | %32,5 | %32,0 |
| Yana vuruş, kaleci ortada | %0 | %0-0,5 | %0 |
| **Genel (Bar-Eli ağırlıklı)** | **%14,7** (Hunter 2018: %16,5) | **%17,4** | **%15,4** |

- Genel oran ve doğru taraf gerçeğe **yaklaştı**; ters taraf yine %0. Fark nereden: erken çıkan kaleci artık top
  gelince yere inmiş oluyor (eskiden 1,55 m'de havada bekliyordu); yüksek toplarda kurtarış azaldı (24 m/s haritası,
  1,7 m: eski %8-33, yeni %5-13; Almeida ve ark. 2016'da üst sıra bölgelerinde kurtarış %0-10), alçak köşelerde
  arttı (x = ±3,3 m, 0,3-1,0 m: eski %0, yeni %17-25; Almeida'da alt köşeler %18-22).
- Harita ve tablo: `../tur3b_olcum/kalibrasyon_SONRA.txt` (önce: `../tur3b_olcum/kalibrasyon_ONCE_eski_motor.txt`).

Yorum: modelin **deseni** gerçeğe uyuyor (ters tarafa atlayan hiç kurtaramıyor, ortada kalan yana gideni hiç
kurtaramıyor, ortada kalan ortaya geleni en çok kurtarıyor). Ama varsayılan kuralla kaleci, doğru tarafa
atladığında gerçeğin yaklaşık iki katı kurtarıyor: 0,248 s'den sonra topun yerini kusursuz biliyor ve dokunduğu topu
hiç kaçırmıyor.

## 4. Hunter menzil-içi durdurma olasılığı (eski provada KAPALI, [tur3 2026-10-22] `config_sablon.json`'da AÇIK)
`keeper_model.in_reach_save_model = {"a": -0.0447, "b": 1.72}` eklenirse, temas olduğunda topun gerçekten
durdurulma olasılığı **P = kırp(−0,0447·v_şut + 1,72)** olur (Hunter 2018: 20 m/s'de %82, 30 m/s'de %38).
Durduramazsa sonuç `goal`, temas `fingertip` ve `"beaten": true` olur. Bu, brief'teki "temas = kurtarış" kuralını
değiştirdiği için eski provada kapalıydı. [tur3 2026-10-22] **Akın kararı (22 Ekim): AÇIK.** Sabitler kodla ve bu
belgeyle tutarlı: kod `p_keep = kırp(a·hız + b)` (hız = şutun çıkış hızı `speed_mps`), `beaten = u_keep ≥ p_keep`;
a = −0,0447, b = 1,72 → 20 m/s %82,6, 26,5 m/s %53,5, 30 m/s %37,9. Ölçülen etkisi (bölüm 3 ile aynı şut kümesi,
`kalibrasyon.py --config config_sablon.json --n 200`): isabetli şutlarda Bar-Eli ağırlıklı kurtarış **%17,4**
(kapalıyken %25,8; gerçek %14,7, Hunter 2018 %16,5). Sinek beyninin gerçek şutlarıyla (yüksek, 25-28 m/s) oran
`../veri/olasilik_tahmini.json`'da. [tur3b 2026-10-22] Balistik kaleciyle yeniden: `_tur3/veri/olasilik_tahmini_tur3b_A.json` (sapma kapalı) ve `_B.json` (sapma açık); özet `_tur3/DEGISIKLIK.md`.

## 5. penalty_log.json: sözleşmeye EK alanlar (eklemeli, hiçbir sözleşme alanı değişmedi)
- Üst düzey: `prova`, `stub`, `UYARI`, `keeper_seeds`, `beacon`, `engine{name,version,sha256}`, `config_sha256`,
  `decisions_sha256`, `decisions_readout_sha256`, `pitch` (direk ekseni x = 3,72, üst direk ekseni y = 2,50, file derinliği,
  kaleci düzlemi z = 0,20). **Godot/Blender direkleri bu eksenlere koymalı**, yoksa direğe yakın şutlar görüntüde direğin içinden geçer.
- `shot`: `aim_effective`, `aim_solved`, `launch_velocity`, `speed_at_goal_line_mps`.
- `keeper`: `start_x`, `leave_drawn_s`, `dive_speed_mps`, `dive_height_adapted`, `seed_uniforms`, `plane_z`,
  `path_fields` ve `path` (60 fps, t = −1,0 s'den başlar): `[t, com_x, com_y, shoulder_x, shoulder_y, hand_x, hand_y, feet_x, feet_y]`.
  Kaleciyi bu noktalardan sürmek, sonucu görüntüyle birebir aynı yapar.
- `keeper.contact` ek: `part` (legs/torso/arm), `depth_cm`, `ball_speed_mps`, `p_catch`, `beaten`, `p_keep`. Gol, ıska ve direkte `contact` = `null`.
- `beyin`: karar dosyasından kopya (`trial_seed`, `steer`, `power_spikes`, `decision_ms`, `scene`).
- `event`: sonucu belirleyen an (`keeper`, `post_left_of_keeper`, `post_right_of_keeper`, `crossbar`, `goal_line`), `t` ve `pos`.
  [tur4 2026-10-23, motor 1.1.1] Ahşap olaylarında (`post_*`, `crossbar`) `type/t/pos` ilk ahşap vuruşudur ve iki EK alan
  vardır: `direkten_gol` (true = top sonra kale çizgisini çerçevenin içinden geçti, `outcome` = `goal`; false = `outcome` =
  `post`) ve `cizgi` (topun çizgiyi geçtiği an ve yer, `{t, pos}`; geçmediyse `null`). **Sonucu her zaman `outcome` söyler**;
  ekrandaki etiket `outcome`'tan gelmeli (direkten golde "GOL", istenirse "direkten gol" alt yazısı). Eski okuyucular bozulmaz.
- Tutulan topun yörüngesi el noktasını izler; çelinen ya da direkten dönen top 0,8 s daha simüle edilir. [tur4 2026-10-23]
  Ahşaptan sonra karar bekleniyorsa (çizgi henüz geçilmedi) bu kesme, top çerçeveye artık değemeyecek kadar önde ve
  kaleden uzaklaşıyor/duruyor olana kadar ertelenir (top kaleye dönebildiği sürece simülasyon sürer, en çok `t_max_s`).
- [tur4 2026-10-23] Çelme kuralı değişmedi: kurtarışta (çelme) top kaleye dönmez; kurtarıştan sonra ahşap ya da çizgi
  sonucu değiştirmez.

## 6. Sınırlar
- Falso/Magnus yok, Cd sabit; rüzgâr yok.
- Kaleci tek düzlemde iki boyutlu bir model; ileri çıkma, el bileği, eldiven yok. Direğe çarpmaz.
- [tur3b] Uçuşta hava direnci yok; iniş ve kayma basit (yarı hız + sabit sürtünme). Kalkış açısı, gövde eğimi, iniş
  kaybı ve sürtünme varsayım (yayımlanmış tek bir sayıları yok); kaynaklı olanlar: kalkış yatay hızı (~3,9-4,2 m/s),
  itme süresi ve yönü, çökme.
- [tur3b] Kaleci kaydıktan sonra yatay olarak direğin dışına taşabilir (yalnız görüntü; çarpışma yok).
- Kaleci RT'den sonra topun geçeceği noktayı kusursuz bilir (kaleci lehine).
- FC reytingi → fizik eğimleri varsayım. Yorgunluk, baskı, şutörün koşusu modelde yok.
- Kurtarılan topun sekişi basitleştirilmiştir (yalnız görüntü).

## 7. [tur3 2026-10-22] Kalecinin yana kayması ve drand beacon (config `keeper_shift`, `beacon`)
- **Kayma:** her şuttan önce kaleci çizgi üzerinde yana kayar: büyüklük düzgün [0,30; 0,50] m, yön %50/%50, mm'ye
  yuvarlanır. Taahhüt anında kimse (Akın dahil) bilemez: sayılar, taahhütten SONRA yayınlanan drand quicknet turu N'nin
  `randomness` değerinden çıkar.
  - anahtar = `"<randomness>|<taahhüt SHA-256>"`; u_b = U(anahtar, `"kick<n>|kayma_buyukluk"`), u_y = U(anahtar, `"kick<n>|kayma_yon"`)
  - U(a, e) = (SHA-256(`"a|e"`) ilk 7 bayt, big-endian + 0,5) / 2⁵⁶ (seed çekilişleriyle aynı fonksiyon)
  - keeper_x = round((+1 eğer u_y < 0,5, değilse −1) · (0,30 + 0,20·u_b), 3). +x = şutörün sağı = kalecinin solu.
  - Hesap: `beacon.py kaymalar` (ve `verify.py` aynısını yeniden hesaplar).
- **Beyin ve motor aynı yeri görür:** beyin `kick.py --keeper-x=<5 kayma>` ile koşar (LC10 girdisi bu x'ten), motor
  karar dosyasındaki `scene.keeper_x`'i okur ve merkeze çekilme 0 olduğu için kaleciyi tam oraya koyar
  (`keeper.start_x = keeper_x`). `penalty_model.py` değişmedi; düzeltme yalnız config'te.
- **Beacon:** drand quicknet (zincir `52db9ba7…`, 3 s'de bir tur, şema bls-unchained-g1-rfc9380). [tur3 2026-10-22] Zincir bilgileri (chain_hash, açık anahtar, genesis, period, şema, relay'ler) `beacon.py`, `commit.py` ve `verify.py` içinde SABİT; config farklıysa HATA, tur saati yalnız sabitlerden hesaplanır. `commit.py yeni` gelecekteki bir tur N seçer (varsayılan 180 dk sonra, final için en az 120 dk) ve config'e yazar; N'nin `randomness`'ı motorun `--beacon` değeridir (kaleci seed'leri: `int(SHA-256("<seed>|beacon|<randomness>")[:15], 16)`, değişmeyen `effective_seeds`).
- **Beyin tohumu da beacon'dan** [tur3 2026-10-22]: seed_base = (SHA-256(`"<randomness>|<taahhüt SHA>|beyin|seed_base"`) ilk 8 onaltılık hane) mod 4·10⁹; şut n'nin tohumu seed_base + n (kick.py kuralı). Config'te seed_base yok.
- **Doğrulama (`verify.py`):** BLS imzası quicknet açık anahtarıyla (`bls12381.py`, RFC 9380); randomness = SHA-256(signature); ulaşılan relay'lerin hiçbiri farklı değer vermiyor ve `/info` sabitlerle aynı; beyin taahhüt + beacon'dan hesaplanan tohum ve yerle yeniden koşturulup birebir karşılaştırılıyor. Ayrıntı: `_tur3/YENI_AKIS.md`.
- **Skor:** gol → SİNEK; kurtarış, direk, aut (wide), üstten aut (over) → ÇAKIR (`skor_kurali`). Her şut sayılır.
  [tur4 2026-10-23] Direkten gol (direk/üst direkten sonra çizgiyi içeriden geçen top) bir GOLDÜR → SİNEK; `post` yalnız
  direkten sonra kaleye girmeyen şut.
- **Positioning 80 ne yapıyor?** Tur3 kurallarıyla motorda hiçbir şey. Değer config'te, log'da ve taahhütte durur;
  ekranda gösterilebilir, ama kalecinin yeri artık kayma kuralından gelir. Reytingi kaymaya bağlayan yayımlanmış bir
  formül yok; 30-50 cm aralığı Akın'ın kararıdır.

## 8. [tur3b 2026-10-22] Şut sapması: SEÇENEK B (varsayılan KAPALI, `config.sut_sapmasi`)
**Neden:** bugüne kadar sinek hiç ıskalamıyordu: beynin nişanı çerçevenin içine kırpılıyor ve vuruş kusursuz uygulanıyordu.
Gerçek oyuncular niyet ettikleri yere tam vuramaz. B açılırsa beynin nişanı **niyet** sayılır, ayak önceden kayıtlı bir
yürütme hatası ekler. A (kapalı) bugünkü davranıştır.

**Kural (sapma-v1, sabit; sonuç görülmeden yazıldı):**
- Zarlar: u1 = U(kseed, `"kick<n>|sapma_u1"`), u2 = U(kseed, `"kick<n>|sapma_u2"`); kseed = şut n'nin **beacon karışmış**
  kaleci seed'i (`effective_seeds`). Yani taahhüdün içindeki seed + taahhütten sonra yayınlanan drand turu: kimse önceden bilemez.
- Box-Muller: z1 = √(−2 ln u1)·cos(2π u2), z2 = √(−2 ln u1)·sin(2π u2) (iki bağımsız standart normal).
- f = kırp(nişan_y / 1,6 m, 0, 1). σx = olcek·(α_h,yer + (α_h,yüksek − α_h,yer)·f)·hız^δ_h, σy aynı biçimde (δ_v, α_v).
- Gerçek nişan = niyet + (σx·z1, σy·z2); motor topu bu noktaya fırlatır (çizgi altına inerse yerden giden şut).
  **Aut, üstten aut ve direk ÇAKIR'a** (skor kuralı değişmedi).
- Log: `shot.sapma` = {kural, u, z, sigma_m, hata_m, nisan_niyet, nisan_gercek}; `shot.aim_effective` = gerçek nişan;
  üst düzeyde `sut_sapmasi_acik`. Aut/direk açıklamasına "Vuruş, sineğin nişanından X saptı." eklenir.

**Sabitler ve kaynakları:**
| Sabit | Değer | Kaynak |
|---|---|---|
| δ_h, α_h (yer / 1,6 m hedef) | 0,5056909; 0,123205 / 0,138678 | Hunter, Angilletta, Pavlic, Lichtwark & Wilson 2018, *J. Biomech.* 72:159-166, Tablo 3; 20 deneyimli oyuncu, 8466 vuruş, 11 m, **iç taraf (side-foot)** |
| δ_v, α_v (yer / 1,6 m hedef) | 2,057649; 0,000594 / 0,001372 | aynı makale, Tablo 4 |
| Biçim | standart sapma = α·hız^δ (hız m/s) | makalenin varyans gücü fonksiyonu; şekil 2-3'teki ±1 SD çizgileriyle kontrol edildi (ör. yerdeki hedef, 25 m/s: dikey SD ~0,45 m) |
| İç taraf seçimi | | sinekte vuruş tekniği yok; iç taraf daha isabetli (daha az sapma: sinek lehine, temkinli seçim); sineğin hızları (24-28 m/s) iç tarafın ulaşabildiği aralıkta (makale: iç tarafla 30 m/s üstü yok) |
| Yükseklik arası | 0 ile 1,6 m arasında doğrusal, 1,6 m üstü yüksek hedef değeri | varsayım (makalede yalnız iki hedef var) |
| **olcek** | **0,432** ([tur4 2026-10-23]; eskisi 0,332) | **gerçek maç verisine kalibrasyon** (aşağıda) |

**Kalibrasyon (`kalibrasyon.py --config config_sablon.json --sapma-kalibre`, 12.000 şut, ortak rastgele sayılarla ikiye bölme):**
- Hedef: maç içi penaltılarda kaleyi bulmayan (aut + üstten aut + direk) oranı **%4,78** = Vollmer, Schoch & Brandes 2024
  (*PLoS One* 19:e0315017; Transfermarkt, 115 yarışma, 2012/13-2022/23): kupalar %4,29 (7.694), ligler %4,94 (23.519).
- Niyet nişanları: bölüm 3'ün standart şut kümesi (bölge içinde x düzgün, yükseklik alçağa yatık, hız N(23,5; 1,9));
  bölgeler Bar-Eli vuruş toplamlarıyla (92 / 82 / 112) ağırlıklı; kaleci gerçek dağılımdan (`draw_plan`).
- Sonuç ([tur4 2026-10-23], motor 1.1.1): olcek 1,0 (laboratuvar hatası olduğu gibi) → %13,7 kaçan; **olcek 0,432 → %4,78**
  (aut %0,33, üstten aut %0,95, direk %3,50). Yani maçtaki profesyoneller laboratuvardaki deneyimli oyunculardan ~2,3 kat
  isabetli (ya da niyetleri çerçeveden daha içeride).
- Kontrol (ayarlamada kullanılmadı): Almeida, Volossovitch & Duarte 2016 (UEFA ŞL + UAL, 536 penaltı; The Guardian'ın
  grafiği): genel %5,2 kaçan; kale üst sırasında ~%13,7, alt sırasında ~%2,7. Model (0,432): üst sıra %11,3, alt sıra %2,0
  (yüksek şutlarda gerçeği biraz **az** tahmin ediyor).
- [tur4 2026-10-23] **Kalibrasyon hatası (dürüst not):** 0,332, motor 1.1.0'ın direkten golleri "direk" saydığı hâliyle
  kalibre edildi. Motor 1.1.1'de (direkten gol = gol) aynı ölçekle kaçan oranı %3,34 (hedef %4,78); düzeltilmiş kuralla %4,78'i
  veren ölçek 0,432. **Seçenek B "gerçek maç verisine (%4,78) kalibre" diye kaydedildiği için ölçek düzeltildi: 0,432**
  (`../_tur3/tur3b_olcum/sapma_kalibrasyon_motor111.txt`, `kalibrasyon_sonuc.txt`). Yeni bir kural değil, kaydedilen kuralın düzeltmesi.
- **Bilinen zayıflık:** (0,332 ile) kaçanların ~%90'ı direkti; 0,432 ile ~%73 (aut %0,33, üstten aut %0,95, direk %3,50); UEFA.com'un
  2007/08-2013/14 ŞL sayımında 211 penaltıda 8 direk, 4 aut (küçük örnek). Sebep: niyet olarak alınan standart küme
  çerçeveye kadar uzanıyor (direğe 11 cm, üst direğe 14 cm). Kaçanların TOPLAM oranı kalibre, ama türleri gerçekten daha
  direk ağırlıklı.
- Sinek için anlamı: sineğin nişanları çerçeveden içeride (yan direğe ~0,5-2 m, üst direğe ~0,8-1,1 m) ve hızlı (25-28
  m/s); bu kuralla tipik bir sinek şutunda σx ≈ 0,32 m, σy ≈ 0,48 m (26,8 m/s, 1,45 m; [tur4] 0,432 ile). Olasılıklar: `../_tur3/DEGISIKLIK.md`.
- **Sonradan ayar yok:** olcek ve bütün α/δ `commit.py`'de (`TUR3B_KURALLARI`) ve `verify.py`'de (KAT) elle yazılı; şablon
  bunlardan saparsa `commit.py` üretmez, `verify.py` HATA verir. A mı B mi, şablondaki `sut_sapmasi.acik` ile seçilir
  ve bir gün önceki duyuru özetine girer.
- Modelde olmayanlar: Hunter'ın bulduğu hızla kayan ortalama (sistematik kayma) ve sağ/sol ayak eğik dağılımı;
  hız hatası (yalnız yön sapıyor); baskı (seri penaltıda kaçan %9,92, Vollmer 2024; sinekte baskı yok, maç içi oran alındı).
