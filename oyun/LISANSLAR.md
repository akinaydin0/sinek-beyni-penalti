# Lisanslar ve kaynaklar (oyun/)

## İndirilen kod ve varlık
Yok. Bu klasörde indirilmiş hiçbir kod, model, görsel, ses ya da veri dosyası yok.
Motor yalnızca Python 3 standart kütüphanesini kullanır (numpy bile yok).

## EA SPORTS FC
- Kullanılan tek şey, brief'te verilen beş reyting sayısı ve boy (Diving 80, Handling 76,
  Kicking 81, Positioning 80, Reflexes 82, 1,91 m). Bunlar config'e elle yazılmış bilgi
  değerleridir; EA'ya ait hiçbir görsel, model, kart, logo ya da ekran görüntüsü kullanılmadı.
- Reytingleri bu klasörde biz doğrulamadık; kaynak alanı brief'ten geldi ("EA SPORTS FC 27 resmi reyting sayfası").

## Bilimsel kaynaklar (yalnızca sayılar alındı, metin kopyalanmadı)
| Kullanıldığı yer | Kaynak | Bağlantı |
|---|---|---|
| Dalış yönü %49,3 / %6,3 / %44,4 ve koşullu kurtarış oranları (kalibrasyon) | Bar-Eli, Azar, Ritov, Keidar-Levin, Schein (2007), *J. Economic Psychology* 28(5):606-621, doi:10.1016/j.joep.2006.12.001 | https://pluto.mscc.huji.ac.il/~msiritov/BarEliAzarRitovKeidarSchein.pdf |
| Çıkış zamanı N(−0,19; 0,145) s, aralık −0,76…0,30 s, dalış hızı 4 m/s, menzil-içi kurtarış P = −0,0447·v + 1,72, şut hızları | Hunter, A. H. (2018), *Predicting soccer penalty success: An optimality model*, doktora tezi, The University of Queensland | https://espace.library.uq.edu.au/view/UQ:25c3141 |
| Ortalama çıkış zamanı −0,19 s (yayımlanmış hâli) | Hunter ve ark. (2022), *Identifying the best strategy for soccer penalty success*, J. Biomechanics | https://www.sciencedirect.com/science/article/abs/pii/S0021929022002512 |
| Çıkış zamanı −0,22 ± 0,11 s (330 penaltı, karşılaştırma) | Hunter, Murphy, Angilletta, Wilson (2018), *Sports* 6(3):73, doi:10.3390/sports6030073 (CC BY) | https://www.mdpi.com/2075-4663/6/3/73 |
| Kıdemli kaleci karar süresi 250-260 ms | Piechota & Majorczyk (2023), *Sensors* 23(9):4483, doi:10.3390/s23094483 | https://pmc.ncbi.nlm.nih.gov/articles/PMC10181563/ |
| Yana dalış en az ~600 ms, üst köşe ~1000 ms (zamanlama kontrolü) | van der Kamp, Dicks, Navia, Noël (2018), *Ger. J. Exerc. Sport Res.* 48:169-175, doi:10.1007/s12662-018-0506-3 | https://link.springer.com/article/10.1007/s12662-018-0506-3 |
| Penaltıların çoğu alçak, %18,8 kurtarış (kalibrasyonda alçak yükseklik dağılımı) | The Guardian datablog (2023, Opta verisiyle) | https://www.theguardian.com/football/datablog/2023/aug/19/how-to-take-penalty-kicks-best-stats-football-soccer-data-womens-world-cup-2023 |
| Top kütlesi/çapı, kale ölçüleri, direk kalınlığı ≤ 12 cm | IFAB Oyun Kuralları, Kural 1-2 | https://www.theifab.com/laws |
| Vücut segment oranları (kol 0,44H, omuz 0,82H, COM ~0,55H) | Drillis & Contini (1966), Winter, *Biomechanics and Motor Control of Human Movement* içinde | — |
| Cd ≈ 0,25 (vuruş hızında) | brief değeri; süperkritik futbol topu ölçümleriyle uyumlu (ör. Goff & Carré 2009, *Am. J. Phys.* 77:1020) | — |

## [tur3 2026-10-22] Açık rastgelelik: drand quicknet
- Kaleci seed'lerine karışan ve kaymaları belirleyen değer, drand ağının (League of Entropy) quicknet zincirinden
  okunan bir turun `randomness` alanıdır (açık, herkese açık veri; indirilmiş kod yok, yalnızca HTTP ile JSON okunur).
- Zincir: `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, belgeler https://docs.drand.love,
  relay'ler https://api.drand.sh, https://api2.drand.sh, https://drand.cloudflare.com.
- [tur3 2026-10-22] BLS imza kontrolü `bls12381.py` içinde, kendi yazdığımız bağımlılıksız saf Python koduyla yapılıyor (kütüphane indirilmedi). Eğri sabitleri ve 11-izojeni katsayıları: RFC 9380 *Hashing to Elliptic Curves* (Faz-Hernandez ve ark., IRTF CFRG, 2023), bölüm 8.8.1 ve Ek E.2; test vektörleri Ek J.9.1 (https://www.rfc-editor.org/rfc/rfc9380.html). RFC metni kopyalanmadı, yalnız sayılar alındı.
- [tur3 2026-10-22] Bağımsız JavaScript kontrolü (`bagimsiz/kontrol.mjs`) yalnız Node.js'in kendi `crypto` modülünü kullanır; paket yok.


## [tur3b 2026-10-22] Balistik kaleci ve şut sapması (yalnız sayılar alındı, metin kopyalanmadı; paket indirilmedi)
| Kullanıldığı yer | Kaynak | Bağlantı |
|---|---|---|
| Kalkış anındaki yatay COM hızı ~3,9 m/s (iki bacağın katkısı 2,7 + 1,2 m/s; 10 elit kaleci, kuvvet platformu) | Ibrahim, Kingma, de Boode, Faber, van Dieën (2019), *J. Sports Sci.* 37(3):313-321, doi:10.1080/02640414.2018.1499413 (yalnız özet okundu) | https://doi.org/10.1080/02640414.2018.1499413 |
| İtmede COM yolu (~0,6-0,7 m), çökme 8-14 cm, ışıktan topa dalış süresi 0,97-1,05 s | Ibrahim ve ark. (2019), *Front. Sports Act. Living* 1:15, doi:10.3389/fspor.2019.00015 (CC BY) | https://www.frontiersin.org/articles/10.3389/fspor.2019.00015 |
| Dalışın itme evresi: önce yan adım, sonra karşı bacak ve aynı taraf bacak itmesi; gövde yana eğik | Ibrahim ve ark. (2020), *Front. Sports Act. Living* 2:13, doi:10.3389/fspor.2020.00013 (CC BY) | https://pmc.ncbi.nlm.nih.gov/articles/PMC7739716/ |
| Şut sapması: standart sapma = α·hız^δ, iç taraf vuruşu, yerdeki ve 1,6 m'deki hedef (Tablo 3-4: δ_h 0,5056909, α_h 0,123205 / 0,138678; δ_v 2,057649, α_v 0,000594 / 0,001372) | Hunter, Angilletta, Pavlic, Lichtwark, Wilson (2018), *J. Biomech.* 72:159-166, doi:10.1016/j.jbiomech.2018.03.003 (kabul edilmiş metin, UQ eSpace). Makale "varyans = α·hız^(2δ)" yazıyor; biz α'yı 1 m/s'deki standart sapma olarak okuduk (şekil 2-3'teki ±1 SD çizgileriyle tutuyor; varyans olarak okunsa dikey SD 25 m/s'de 18 m çıkardı) | https://espace.library.uq.edu.au/view/UQ:725550 |
| Kalibrasyon hedefi: maç içi penaltılarda kaçan (gol ve kurtarış dışı) kupalarda %4,29 (7.694), liglerde %4,94 (23.519); seri penaltıda %9,92 (14.189) | Vollmer, Schoch, Brandes (2024), *PLoS One* 19(12):e0315017, doi:10.1371/journal.pone.0315017 (CC BY) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11627389/ |
| Kontrol: 536 UEFA kulüp penaltısında %5,2 kaçan, %18,8 kurtarış; bölge bölge gol/kurtarış/kaçan yüzdeleri | Almeida, Volossovitch, Duarte (2016), *Int. J. Perf. Anal. Sport*; sayılar makaleden değil, The Guardian'ın bu makaleye dayanan grafiğinden okundu | https://interactive.guim.co.uk/embed/2023/08/ai2html-output_penalties-placement |
| Kontrol: 211 Şampiyonlar Ligi penaltısında (2007/08-2013/14) 8 direk, 4 aut, 43 kurtarış | UEFA.com, S. Hart & R. Esteva (21 Ekim 2014), "Penalties: How to hit them, where to put them" (editoryal analiz) | https://www.uefa.com/uefachampionsleague/news/025a-0ea75351191f-7aaf2e07ac3e-1000--penalties-how-to-hit-them-where-to-put-them/ |
