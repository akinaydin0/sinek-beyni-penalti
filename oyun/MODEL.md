# Penaltı motoru: formüller, sabitler, kaynaklar

Bütün sayılar `config_*.json` içinde durur ve taahhüt özetine girer. Kod (`penalty_model.py`) yalnızca algoritmadır.
Koordinatlar `SOZLESME.md` ile aynı: x+ şutörün sağı (= kalecinin SOLU), y yukarı, z kaleden penaltı noktasına.
Kaleci için "left/right" her yerde **kalecinin kendi** solu/sağıdır (Bar-Eli 2007 ile aynı).

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
| Direk teması | top merkezi ile direk ekseni arası < 0,17 m → `post` (üst direk dahil). Sekme: dik bileşen ×0,6, teğet ×0,9 | brief kuralı; katsayılar varsayım |
| Gol / ıska | kaleci ve direk teması yoksa, z = 0'da merkez içerideyse `goal`; dışarıdaysa `wide` ya da `over` (hangi yönde daha çok taşıyorsa) | |
| File | 1,5 m derin kutu, çok düşük sekme | yalnız görüntü |

## 2. Kaleci (Uğurcan Çakır: Diving 80, Handling 76, Kicking 81, Positioning 80, Reflexes 82, boy H = 1,91 m)
FC reytingleri oyun değerleridir, laboratuvar ölçümü değildir. **Reytingi fiziğe çeviren yayımlanmış bir formül yok**;
aşağıdaki eğimler bizim varsayımımız, dayandıkları temel değerler kaynaklıdır.

| Ne | Formül | Uğurcan | Kaynak |
|---|---|---|---|
| Tepki süresi (Reflexes) | RT = 255 − 0,4·(Reflexes − 65) ms | **0,248 s** | Piechota & Majorczyk 2023: kıdemli kaleciler 250-260 ms. Referans 65 ve 0,4 ms/puan varsayım |
| Dalış hızı (Diving) | v = 4,0·(1 + 0,01·(Diving − 75)) m/s | **4,2 m/s** | Hunter 2018 dalış modelinde 4 m/s; puan eğimi varsayım |
| İtme evresi | 0,40 s boyunca sabit ivme (a = v/0,40), sonra sabit hız | tam uzanma ≈ 0,57 s | varsayım; van der Kamp ve ark. 2018: yana dalış en az ~600 ms |
| Ağırlık merkezi en uzun yol (Diving + boy) | S = H·(0,795 + 0,003·(Diving − 75)) | 1,55 m | varsayım |
| Gövde oranları | COM yüksekliği 0,52H; COM→ayak 0,52H; COM→omuz 0,27H; kol 0,44H | | Drillis & Contini 1966 |
| Tam uzanma erişimi | reach = S + 0,71H | **2,90 m** | brief (~2,9 m) |
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

### Hareket
- **Atlayan kaleci** `leave_time_s` anında, seed'in seçtiği tarafa, 10° yukarı açıyla harekete başlar. İtme bitene
  (leave + 0,40 s) kadar topu göremediyse dalış yüksekliği değişmez. Görebildiyse yalnızca **yüksekliği** topa göre seçer
  (−35°…+45°); **tarafı asla değiştiremez**.
- **Ağırlık merkezi**: p(τ) = ½aτ² (τ ≤ 0,40 s), sonra p = ½v·0,40 + v·(τ − 0,40), en çok S. Dikeyde en çok +0,45 m
  (dikey sıçrama sınırı, varsayım). Tam uzanmadan sonra yerçekimiyle düşer, yatınca COM 0,15 m.
  İtme sırasında basan ayak yerde kalır.
- **Ortada kalan kaleci** (`stay`) topu RT anında görür ve topun geçeceği noktaya doğru gereken kadar hareket eder
  (kol erişiminin %90'ı düşülerek). Bu durumda `leave_time_s` = RT.
- **Eller**: RT'den önce dalışla birlikte başın üstüne uzanır. RT'den sonra el, topun kaleci düzlemini keseceği
  noktaya doğru gövdeye göre en çok 4 m/s hızla gider; kol boyunu aşamaz (varsayım).
- **Temas**: kaleci düzleminde (z = 0,20 m) top merkezi ile üç kapsül arasındaki en kısa mesafe hesaplanır:
  bacaklar (ayak→COM, r = 0,10), gövde (COM→omuz, r = 0,16), kol ve eller (omuz→el, r = 0,08).
  **boşluk = mesafe − r_parça − 0,11 m**. boşluk ≤ 0 → kurtarış (brief kuralı).
- **Tür**: kol ucunda ve derinlik < 6 cm → `fingertip`; bacak → `parry`; değilse Handling zarı: u < p_tut → `catch`, değilse `parry`.
  Çelinen top kaleye girmez (kaleci düzlemi çizgiden 20 cm önde olduğu için top dışarı itilir).
- **margin_cm**: gol ve direkte kalecinin kaç cm yetişemediği; kurtarışta topun ne kadar içeriden karşılandığı;
  `wide`/`over`'da topun çerçevenin kaç cm dışından geçtiği. (`keeper_gap_cm` her durumda kalecinin boşluğudur; eksi = temas.)
- **explain**: bu sayılardan kurulan tek Türkçe cümle (`explain_tr`).

## 3. Kalibrasyon (yalnız PROVA kontrolü, `kalibrasyon_sonuc.txt`)
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
`../veri/olasilik_tahmini.json`'da.

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
- Tutulan topun yörüngesi el noktasını izler; çelinen ya da direkten dönen top 0,8 s daha simüle edilir.

## 6. Sınırlar
- Falso/Magnus yok, Cd sabit; rüzgâr yok.
- Kaleci tek düzlemde iki boyutlu bir model; ileri çıkma, el bileği, eldiven yok. Direğe çarpmaz.
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
- **Positioning 80 ne yapıyor?** Tur3 kurallarıyla motorda hiçbir şey. Değer config'te, log'da ve taahhütte durur;
  ekranda gösterilebilir, ama kalecinin yeri artık kayma kuralından gelir. Reytingi kaymaya bağlayan yayımlanmış bir
  formül yok; 30-50 cm aralığı Akın'ın kararıdır.
