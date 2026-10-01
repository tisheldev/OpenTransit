# API-backed M4 search review

- Captured: 2026-10-01T06:56:57.896343+00:00
- Generation: 12bfd861a952535fbc8f094b9a13d93fd47d6efd564b272edbb44f378a25d9c0
- First-pass top-1: 130/183
- First-pass top-5: 150/183
- Human H4 verdict: 

Mechanical outcomes only; no human verdict or failure cause is assigned.

| Case | Variant | Query | Expected place | Lang | Script | Category | Outcome | Score rule | Top 1 mechanical | Top 5 mechanical | Top result | Kind | Address level | Precision | Result language | Distance m | H4 usability | H4 verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|
| P001 | primary | Tel Aviv Savidor Center | TA Savidor | en | latin | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P002 | primary | תחנת רכבת תל אביב סבידור מרכז | TA Savidor | he | hebrew | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P003 | primary | HaShalom Station | TA HaShalom | en | latin | station | success | haversine_within_original_tolerance | hit | hit | HaShalom Rail Station | stop |  |  | en | 52.70099216892036 |  |  |
| P004 | primary | תחנת השלום | TA HaShalom | he | hebrew | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P005 | primary | Yitzhak Navon | JLM Navon | en | latin | station | success | haversine_within_original_tolerance | miss | miss | Yitzhak Navon/HaBanim | stop |  |  | en | 100147.13261286539 |  |  |
| P006 | primary | תחנת יצחק נבון | JLM Navon | he | hebrew | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P007 | primary | Haifa Center HaShmona | Haifa Center | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Haifa Center HaShmona Train Station | stop |  |  | en | 158.18702790874832 |  |  |
| P008 | primary | חיפה מרכז השמונה | Haifa Center | he | hebrew | station | success | haversine_within_original_tolerance | hit | hit | תחנת רכבת חיפה מרכז השמונה | stop |  |  | he | 158.18702790874832 |  |  |
| P009 | primary | Beersheba Central Station | BS Central | en | latin | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P010 | primary | באר שבע מרכז | BS Central | he | hebrew | station | success | haversine_within_original_tolerance | hit | hit | באר שבע מרכז | stop |  |  | he | 26.60147970695925 |  |  |
| P011 | primary | Ben Gurion Airport | TLV Airport | en | latin | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P012 | primary | נמל תעופה בן גוריון | TLV Airport | he | hebrew | station | success | haversine_within_original_tolerance | miss | hit | האירוסים/רקפת | stop |  |  | he | 3163.4188293488974 |  |  |
| P013 | primary | Herzliya Station | Herzliya | en | latin | station | success | haversine_within_original_tolerance | miss | miss | Herzliya Marina Taxi Station | stop |  |  | en | 2009.7241531527914 |  |  |
| P014 | primary | Modi'in Center | Modiin Center | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Modi'in Railway Station/Center | stop |  |  | en | 231.56037428074072 |  |  |
| P015 | primary | Nahariya | Nahariya | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Nahariya | stop |  |  | en | 555.2522181240255 |  |  |
| P016 | primary | Ashdod Ad Halom | Ashdod Ad Halom | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Ashdod Ad Halom East Rail Station/Alight | station |  |  | en | 75.7152054385736 |  |  |
| P017 | primary | Bat Galim | Bat Galim | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Bat Galim | stop |  |  | en | 0.0 |  |  |
| P018 | primary | Jerusalem Central Bus Station | JLM CBS | en | latin | station | success | haversine_within_original_tolerance | hit | hit | Jerusalem Central Bus Station 3rd Floor/Platforms | station |  |  | en | 108.81465823252908 |  |  |
| P019 | primary | תחנה מרכזית ירושלים | JLM CBS | he | hebrew | station | success | haversine_within_original_tolerance | hit | hit | תחנת מוניות ירושלים תחנה מרכזית | stop |  |  | he | 147.82656825024065 |  |  |
| P020 | primary | Petah Tikva Kiryat Arye | PT Kiryat Arye | en | latin | station | valid_empty | haversine_within_original_tolerance | miss | miss |  |  |  |  |  |  |  |  |
| P021 | primary | Technion | Technion | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | Technion Obelisk | poi |  |  | en | 113.11349263884567 |  |  |
| P022 | primary | הטכניון | Technion | he | hebrew | poi_university | success | haversine_within_original_tolerance | miss | hit | הטכניון | poi |  |  | he | 81376.93041132163 |  |  |
| P023 | primary | Tel Aviv University | TAU | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | Tel Aviv University | poi |  |  | en | 69.02433344608852 |  |  |
| P024 | primary | אוניברסיטת תל אביב | TAU | he | hebrew | poi_university | success | haversine_within_original_tolerance | hit | hit | אוניברסיטת תל אביב | poi |  |  | he | 69.02433344608852 |  |  |
| P025 | primary | Hebrew University Mount Scopus | HUJI Scopus | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | Hebrew University - Mount Scopus | poi |  |  | en | 263.7742641966487 |  |  |
| P026 | primary | Ben Gurion University | BGU | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | Ben Gurion University of the Negev | poi |  |  | en | 344.75114207345695 |  |  |
| P027 | primary | Bar-Ilan University | Bar-Ilan | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | Bar Ilan University | poi |  |  | en | 575.2960341718806 |  |  |
| P028 | primary | Haifa University | Haifa U | en | latin | poi_university | success | haversine_within_original_tolerance | hit | hit | University of Haifa | poi |  |  | en | 554.626292404587 |  |  |
| P029 | primary | Weizmann Institute | Weizmann | en | latin | poi_university | success | haversine_within_original_tolerance | miss | miss | Weizmann Institute Yatir Research Site | poi |  |  | en | 66544.15461624516 |  |  |
| P030 | primary | Ichilov | Sourasky | en | latin | poi_hospital | success | haversine_within_original_tolerance | hit | hit | Ichilov helipad | poi |  |  | en | 51.84347500781627 |  |  |
| P031 | primary | איכילוב | Sourasky | he | hebrew | poi_hospital | success | haversine_within_original_tolerance | hit | hit | בי"ח איכילוב | poi |  |  | he | 168.76078775043956 |  |  |
| P032 | primary | Beilinson Hospital | Beilinson | en | latin | poi_hospital | success | haversine_within_original_tolerance | hit | hit | Beilinson Hospital | poi |  |  | en | 209.92814757369734 |  |  |
| P033 | primary | Rambam Medical Center | Rambam | en | latin | poi_hospital | success | haversine_within_original_tolerance | miss | miss | Ramat Hasharon Medical Center (Macabi) | poi |  |  | en | 78523.2502579069 |  |  |
| P034 | primary | Hadassah Ein Kerem | Hadassah EK | en | latin | poi_hospital | success | haversine_within_original_tolerance | hit | hit | Hadassah Ein Kerem | poi |  |  | en | 245.49153320037584 |  |  |
| P035 | primary | Dizengoff Center | Dizengoff Ctr | en | latin | poi_mall | success | haversine_within_original_tolerance | hit | hit | Dizengoff Center | poi |  |  | en | 112.56683930569356 |  |  |
| P036 | primary | דיזנגוף סנטר | Dizengoff Ctr | he | hebrew | poi_mall | success | haversine_within_original_tolerance | hit | hit | דיזנגוף סנטר | poi |  |  | he | 112.56683930569356 |  |  |
| P037 | primary | Azrieli Center | Azrieli | en | latin | poi_mall | success | haversine_within_original_tolerance | hit | hit | Azrieli Center | poi |  |  | en | 84.76788544021743 |  |  |
| P038 | primary | Malha Mall | Malha | en | latin | poi_mall | success | haversine_within_original_tolerance | hit | hit | Malcha Mall | poi |  |  | en | 93.48050012168757 |  |  |
| P039 | primary | Mahane Yehuda Market | Mahane Yehuda | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Hachapuria Mahane Yehuda Market | poi |  |  | en | 71.68677990712432 |  |  |
| P040 | primary | Western Wall | Kotel | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Western Wall | poi |  |  | en | 30.220326493117724 |  |  |
| P041 | primary | הכותל המערבי | Kotel | he | hebrew | poi_landmark | success | haversine_within_original_tolerance | hit | hit | הכותל המערבי | poi |  |  | he | 30.220326493117724 |  |  |
| P042 | primary | Jaffa Clock Tower | Jaffa Clock | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Jaffa Clock Tower- Pop Up Center | poi |  |  | en | 448.17526590465945 |  |  |
| P043 | primary | מגדל השעון יפו | Jaffa Clock | he | hebrew | poi_landmark | success | haversine_within_original_tolerance | hit | hit | מגדל השעון יפו | poi |  |  | he | 394.91685564274206 |  |  |
| P044 | primary | Yad Vashem | Yad Vashem | en | latin | poi_landmark | success | haversine_within_original_tolerance | miss | hit | Heichal Yad Vashem | poi |  |  | en | 42392.952081957694 |  |  |
| P045 | primary | Mount Herzl | Har Herzl | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Mount Herzl | poi |  |  | en | 142.15177074170984 |  |  |
| P046 | primary | Sarona Market | Sarona | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Sarona Market | poi |  |  | en | 66.67741932662487 |  |  |
| P047 | primary | Habima Theatre | Habima | en | latin | poi_landmark | success | haversine_within_original_tolerance | miss | miss | HaSimta Theatre | poi |  |  | en | 3416.0278390412554 |  |  |
| P048 | primary | Bloomfield Stadium | Bloomfield | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Bloomfield Stadium | poi |  |  | en | 101.08359824184086 |  |  |
| P049 | primary | Masada | Masada | en | latin | poi_landmark | success | haversine_within_original_tolerance | miss | hit | Masada | poi |  |  | en | 169540.8099996208 |  |  |
| P050 | primary | Mitzpe Ramon | Mitzpe Ramon | en | latin | poi_landmark | success | haversine_within_original_tolerance | hit | hit | Mitzpe Ramon | poi |  |  | en | 223.73849625601733 |  |  |
| P051 | primary | Dizengoff 100 Tel Aviv | Dizengoff St | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Dizengoff 100, תל־אביב–יפו | address | house_number | address_node | en | 12.145925376679035 |  |  |
| P052 | primary | דיזנגוף 100 תל אביב | Dizengoff St | he | hebrew | address | success | haversine_within_original_tolerance | hit | hit | דיזנגוף 100, תל־אביב–יפו | address | house_number | address_node | he | 12.145925376679035 |  |  |
| P053 | primary | Rothschild Boulevard 1 Tel Aviv | Rothschild | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Sderot Rothschild 1, תל אביב-יפו | address | house_number | address_node | en | 120.06544358717505 |  |  |
| P054 | primary | שדרות רוטשילד 1 תל אביב | Rothschild | he | hebrew | address | success | haversine_within_original_tolerance | hit | hit | שדרות רוטשילד 1, תל אביב-יפו | address | house_number | address_node | he | 120.06544358717505 |  |  |
| P055 | primary | Ibn Gabirol 30 Tel Aviv | Ibn Gabirol | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Ibn Gabirol 30, תל־אביב–יפו | address | house_number | address_node | en | 600.321426249187 |  |  |
| P056 | primary | Jaffa Street 97 Jerusalem | Jaffa St JLM | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Jaffa 97, ירושלים \| القدس | address | house_number | address_node | en | 421.24125455509716 |  |  |
| P057 | primary | יפו 97 ירושלים | Jaffa St JLM | he | hebrew | address | success | haversine_within_original_tolerance | hit | hit | יפו 97, ירושלים \| القدس | address | house_number | address_node | he | 421.24125455509716 |  |  |
| P058 | primary | King George 15 Jerusalem | King George | en | latin | address | success | haversine_within_original_tolerance | hit | hit | King George 15, ירושלים \| القدس | address | house_number | address_node | en | 208.26999817802468 |  |  |
| P059 | primary | Herzl 50 Haifa | Herzl Haifa | en | latin | address | success | haversine_within_original_tolerance | miss | miss | Herzl 50, חיפה | address | house_number | address_node | en | 1088.7193588079695 |  |  |
| P060 | primary | Ben Yehuda 20 Tel Aviv | Ben Yehuda TA | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Ben Yehuda 20, תל־אביב–יפו | address | house_number | address_node | en | 455.5671830832767 |  |  |
| P061 | primary | Allenby 40 Tel Aviv | Allenby | en | latin | address | success | haversine_within_original_tolerance | miss | miss | Allenby 40, תל־אביב–יפו | address | house_number | address_node | en | 785.8830943788963 |  |  |
| P062 | primary | HaNevi'im 20 Jerusalem | HaNeviim | en | latin | address | success | haversine_within_original_tolerance | miss | miss | HaNeviim 20, ירושלים \| القدس | address | house_number | address_node | en | 716.2626226750721 |  |  |
| P063 | primary | Sokolov 30 Ramat Gan | Sokolov RG | en | latin | address | success | haversine_within_original_tolerance | miss | miss | Sokolov 30, רמת גן | address | house_number | address_node | en | 1327.5674073237374 |  |  |
| P064 | primary | Rager Boulevard Beersheba | Rager Blvd | en | latin | address | success | haversine_within_original_tolerance | miss | miss | Yitzhack Rager Avenue | address | street | street_way_midpoint | en | 1040.050579759611 |  |  |
| P065 | primary | הרצל 50 חיפה | Herzl Haifa | he | hebrew | address | success | haversine_within_original_tolerance | miss | miss | הרצל 50, חיפה | address | house_number | address_node | he | 1088.7193588079695 |  |  |
| P066 | primary | Florentin | Florentin TA | en | latin | neighborhood | success | haversine_within_original_tolerance | miss | hit | Florentin | poi |  |  | en | 26291.108092862094 |  |  |
| P067 | primary | פלורנטין | Florentin TA | he | hebrew | neighborhood | success | haversine_within_original_tolerance | miss | hit | פלורנטין | poi |  |  | he | 26291.108092862094 |  |  |
| P068 | primary | Neve Tzedek | Neve Tzedek | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Neve Tzedek | poi |  |  | en | 730.7078763582185 |  |  |
| P069 | primary | Ramat Aviv | Ramat Aviv | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Ramat Aviv | poi |  |  | en | 287.3087800893639 |  |  |
| P070 | primary | Rehavia | Rehavia JLM | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Rehavia | poi |  |  | en | 104.27361099138133 |  |  |
| P071 | primary | Nachlaot | Nachlaot | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Nachla'ot | poi |  |  | en | 227.1245742868573 |  |  |
| P072 | primary | Hadar HaCarmel | Hadar | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Hadar HaCarmel | poi |  |  | en | 243.38989740275602 |  |  |
| P073 | primary | Ramot | Ramot JLM | en | latin | neighborhood | success | haversine_within_original_tolerance | miss | hit | Ramot | poi |  |  | en | 123682.85664925033 |  |  |
| P074 | primary | Old City Jerusalem | Old City | en | latin | neighborhood | success | haversine_within_original_tolerance | hit | hit | Old City | poi |  |  | en | 255.37341243376744 |  |  |
| P075 | primary | העיר העתיקה ירושלים | Old City | he | hebrew | neighborhood | success | haversine_within_original_tolerance | hit | hit | העיר העתיקה | poi |  |  | he | 255.37341243376744 |  |  |
| P076 | primary | Dizengof Center | Dizengoff Ctr | en | latin | misspelling | success | haversine_within_original_tolerance | hit | hit | Dizengoff Center/Dizengoff | stop |  |  | en | 83.16022635821096 |  |  |
| P077 | primary | Technyon | Technion | en | latin | misspelling | success | haversine_within_original_tolerance | hit | hit | Derech Ha'technion | address | street | street_way_midpoint | en | 797.2973979559855 |  |  |
| P078 | primary | Jerusalim | Jerusalem | en | latin | misspelling | success | haversine_within_original_tolerance | miss | hit | Jerusalem | address | street | street_way_midpoint | en | 68968.99947020014 |  |  |
| P079 | primary | Beer Sheva | BS Central | en | latin | misspelling | success | haversine_within_original_tolerance | hit | hit | Be'er Sheva Central Station/Alight | stop |  |  | en | 205.5479402289003 |  |  |
| P080 | primary | Herzliyya | Herzliya | en | latin | misspelling | success | haversine_within_original_tolerance | miss | hit | Herzliya | address | street | street_way_midpoint | en | 74165.85948295894 |  |  |
| P081 | primary | Netania | Netanya | en | latin | misspelling | success | haversine_within_original_tolerance | miss | miss | Netafim | address | street | street_way_midpoint | en | 16438.155820233227 |  |  |
| P082 | primary | Rishon Lezion | Rishon | en | latin | misspelling | success | haversine_within_original_tolerance | miss | miss | HaMishna/Rishon LeZion | stop |  |  | en | 24449.922991386866 |  |  |
| P083 | primary | Savidor Merkaz | TA Savidor | en | latin | misspelling | success | haversine_within_original_tolerance | miss | miss | Merkaz Omen | poi |  |  | en | 67796.67086849731 |  |  |
| P084 | primary | Ben Gurion Airoport | TLV Airport | en | latin | misspelling | success | haversine_within_original_tolerance | miss | miss | Ben Gurion | address | street | street_way_midpoint | en | 80888.38376612506 |  |  |
| P085 | primary | Machne Yehuda | Mahane Yehuda | en | latin | misspelling | success | haversine_within_original_tolerance | miss | hit | Malchee Yehuda | address | street | street_way_midpoint | en | 55183.74473635373 |  |  |
| P086 | primary | Petah Tikva | Petah Tikva | en | latin | translit | success | haversine_within_original_tolerance | miss | hit | Petah Tikva A | stop |  |  | en | 44217.64166982459 |  |  |
| P087 | primary | Petach Tikwa | Petah Tikva | en | latin | translit | success | haversine_within_original_tolerance | miss | miss | Petach Tikvah | address | street | street_way_midpoint | en | 26279.510841282892 |  |  |
| P088 | primary | Petah Tiqwa | Petah Tikva | en | latin | translit | success | haversine_within_original_tolerance | miss | hit | Petah Tiqwa | poi |  |  | en | 3192.9916117227876 |  |  |
| P089 | primary | Rishon LeTsiyon | Rishon | en | latin | translit | success | haversine_within_original_tolerance | miss | hit | Rishon LeTsiyon Beach | stop |  |  | en | 7532.216655995956 |  |  |
| P090 | primary | Rishon LeZion | Rishon | en | latin | translit | success | haversine_within_original_tolerance | miss | miss | HaMishna/Rishon LeZion | stop |  |  | en | 24449.922991386866 |  |  |
| P091 | primary | Kfar Saba | Kfar Saba | en | latin | translit | success | haversine_within_original_tolerance | hit | hit | Kfar Saba | stop |  |  | en | 1297.4433882819671 |  |  |
| P092 | primary | Kefar Sava | Kfar Saba | en | latin | translit | success | haversine_within_original_tolerance | hit | hit | Walk In - Kefar Sava | poi |  |  | en | 1940.342158017333 |  |  |
| P093 | primary | Akko | Akko | en | latin | translit | success | haversine_within_original_tolerance | hit | hit | Akko Central Station/HaArbaa Road | station |  |  | en | 238.50165354506132 |  |  |
| P094 | primary | Acre | Akko | en | latin | translit | success | haversine_within_original_tolerance | hit | hit | Acre | stop |  |  | en | 99.27360220392241 |  |  |
| P095 | primary | Central Station | TA CBS | en | latin | near_dependent | success | haversine_within_original_tolerance | miss | miss | Central Station | stop |  |  | en | 32393.560879165634 |  |  |
| P096 | primary | Central Station | JLM CBS | en | latin | near_dependent | success | haversine_within_original_tolerance | hit | hit | Central Station | stop |  |  | en | 52.38404287622139 |  |  |
| P097 | primary | Herzl | Herzl TA area | en | latin | near_dependent | success | haversine_within_original_tolerance | hit | hit | Herzl/Yehuda Halevi | stop |  |  | en | 2020.7995309721607 |  |  |
| P098 | primary | Herzl | Herzl Haifa | en | latin | near_dependent | success | haversine_within_original_tolerance | hit | hit | Herzl/HaNevi'im | stop |  |  | en | 355.9401385802497 |  |  |
| P099 | primary | HaTachana | HaTachana TA | en | latin | near_dependent | success | haversine_within_original_tolerance | miss | miss | HaTahana | address | street | street_way_midpoint | en | 17478.961562188422 |  |  |
| P100 | primary | University | Haifa U | en | latin | near_dependent | success | haversine_within_original_tolerance | hit | hit | University/I.B.M | stop |  |  | en | 521.6562134696251 |  |  |
| V001 | native | אוטו חולון |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | אוטו חולון | poi |  |  | he | 0.03932116610292634 |  |  |
| V002 | native | יין בכרם |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | יין בכרם | poi |  |  | he | 0.05270134548388047 |  |  |
| V003 | native | מוזנר |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מוזנר | poi |  |  | he | 0.058300832467527174 |  |  |
| V004 | native | תאטרובר |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | תאטרובר | poi |  |  | he | 0.01111949242549315 |  |  |
| V005 | native | HaShdera |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | HaShdera | poi |  |  | en | 0.04382224574370014 |  |  |
| V006 | native | Old Jaffa |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Old Jaffa | poi |  |  | en | 0.06717254272858396 |  |  |
| V007 | native | Satchmo Bar |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Satchmo Bar | poi |  |  | en | 0.05270293002065826 |  |  |
| V008 | native | Zigi |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Zigi | poi |  |  | en | 0.03839785526651225 |  |  |
| V009 | native | ארומה |  | he | hebrew | venue | success | haversine_within_original_tolerance | miss | miss | ארומה | poi |  |  | he | 58177.33063162433 |  |  |
| V010 | native | בית קפה הפינה |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | בית קפה הפינה | poi |  |  | he | 0.030172190651723992 |  |  |
| V011 | native | דדה |  | he | hebrew | venue | success | haversine_within_original_tolerance | miss | hit | דדה | poi |  |  | he | 10747.727939720058 |  |  |
| V012 | native | דה לה פה |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | דה לה פה | poi |  |  | he | 0.034668600681662706 |  |  |
| V013 | native | רולדין |  | he | hebrew | venue | success | haversine_within_original_tolerance | miss | miss | רולדין | poi |  |  | he | 26500.83683739314 |  |  |
| V014 | native | Cafeneto |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Cafeneto | poi |  |  | en | 0.035944572509848935 |  |  |
| V015 | native | Grand Cafe Torquise |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Grand Cafe Torquise | poi |  |  | en | 0.062365199720064664 |  |  |
| V016 | native | Jaw Cafe |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Jaw Cafe | poi |  |  | en | 0.01111949242549315 |  |  |
| V017 | native | Tony Ice |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Tony Ice | poi |  |  | en | 0.058230384491703396 |  |  |
| V018 | native | Yabous Cafe |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Yabous Cafe | poi |  |  | en | 0.05276092615659291 |  |  |
| V019 | native | יעקב קבב |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | יעקב קבב | poi |  |  | he | 0.021747200813983066 |  |  |
| V020 | native | מרכז החומוס והפול |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מרכז החומוס והפול | poi |  |  | he | 0.05638994377428634 |  |  |
| V021 | native | סיפורו של שניצל |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | סיפורו של שניצל | poi |  |  | he | 0.038018204022903804 |  |  |
| V022 | native | רד meat |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | רד meat | poi |  |  | he | 0.039299813478170006 |  |  |
| V023 | native | Burgersbar |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Burgersbar | poi |  |  | en | 0.021933317967847282 |  |  |
| V024 | native | Cofizz |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Cofizz | poi |  |  | en | 0.024152063286368635 |  |  |
| V025 | native | Falafel HaZkenim |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Falafel HaZkenim | poi |  |  | en | 0.030159311709074134 |  |  |
| V026 | native | street food |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | street food | poi |  |  | en | 0.04830586395214915 |  |  |
| V027 | native | דלי קרים |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | דלי קרים | poi |  |  | he | 0.05270857760955802 |  |  |
| V028 | native | מוסלין |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מוסלין | poi |  |  | he | 0.039414912141164195 |  |  |
| V029 | native | Golda |  | he | latin | venue | success | haversine_within_original_tolerance | miss | hit | Golda | poi |  |  | en | 4578.100126832701 |  |  |
| V030 | native | מועדון הבארבי |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מועדון הבארבי | poi |  |  | he | 0.024153576946739516 |  |  |
| V031 | native | studio B |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | studio B | poi |  |  | en | 0.0582954001690779 |  |  |
| V032 | native | הארבעה |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | הארבעה | poi |  |  | he | 0.02188119368919134 |  |  |
| V033 | native | מאש |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מאש | poi |  |  | he | 0.029146508781283303 |  |  |
| V034 | native | רודיאו |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | רודיאו | poi |  |  | he | 0.030161922789237773 |  |  |
| V035 | native | Beer Bazaar Habima |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Beer Bazaar Habima | poi |  |  | en | 0.04546507516069934 |  |  |
| V036 | native | كازية يونس |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | كازية يونس | poi |  |  | ar | 0.04833053517409405 |  |  |
| V037 | native | בית הפנקייק המקורי |  | he | hebrew | venue | success | haversine_within_original_tolerance | miss | hit | בית הפנקייק המקורי | poi |  |  | he | 9467.850015833597 |  |  |
| V038 | native | הלב הרחב |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | הלב הרחב | poi |  |  | he | 0.03856265116934941 |  |  |
| V039 | native | לנדוור |  | he | hebrew | venue | success | haversine_within_original_tolerance | miss | hit | לנדוור | poi |  |  | he | 88382.13367409461 |  |  |
| V040 | native | מסעדת אמא |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מסעדת אמא | poi |  |  | he | 0.029187625172965543 |  |  |
| V041 | native | מסעדת מלון אמריקנה |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | מסעדת מלון אמריקנה | poi |  |  | he | 0.022238985558309388 |  |  |
| V042 | native | פינת הצלע |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | פינת הצלע | poi |  |  | he | 0.045465976249522116 |  |  |
| V043 | native | Alibi |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Alibi | poi |  |  | en | 0.009421643576805262 |  |  |
| V044 | native | Denis Kingdom |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Denis Kingdom | poi |  |  | en | 0.05643270450009103 |  |  |
| V045 | native | Nafoura |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Nafoura | poi |  |  | en | 0.029188820647802316 |  |  |
| V046 | native | Oasis |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | Oasis | poi |  |  | en | 0.052701552528252524 |  |  |
| V047 | native | Pizza Hut |  | he | latin | venue | success | haversine_within_original_tolerance | miss | miss | Pizza Hut | poi |  |  | en | 10411.024979770851 |  |  |
| V048 | native | الرضا |  | he | latin | venue | success | haversine_within_original_tolerance | hit | hit | الرضا | poi |  |  | ar | 0.058130007606391566 |  |  |
| V001:alt_query_en | alt_query_en | Otto Holon |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Otto Holon | poi |  |  | en | 0.03932116610292634 |  |  |
| V002:alt_query_en | alt_query_en | Wine Bakerem |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Wine Bakerem | poi |  |  | en | 0.05270134548388047 |  |  |
| V003:alt_query_en | alt_query_en | Armadillo Kitchen Bar |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Armadillo Kitchen Bar | poi |  |  | en | 0.058300832467527174 |  |  |
| V004:alt_query_en | alt_query_en | Teatrobar |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Teatrobar | poi |  |  | en | 0.01111949242549315 |  |  |
| V007:alt_query_he | alt_query_he | סאצ'מו |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | סאצ'מו | poi |  |  | he | 0.05270293002065826 |  |  |
| V009:alt_query_en | alt_query_en | Aroma |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | miss | miss | Aroma | poi |  |  | en | 50776.61527801738 |  |  |
| V011:alt_query_en | alt_query_en | Dede |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Dede | poi |  |  | en | 0.1725594233463734 |  |  |
| V012:alt_query_en | alt_query_en | de la Paix |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | de la Paix | poi |  |  | en | 0.034668600681662706 |  |  |
| V013:alt_query_en | alt_query_en | Roladin |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | miss | miss | Roladin | poi |  |  | en | 21041.36079245886 |  |  |
| V022:alt_query_en | alt_query_en | Red Meat |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Red Meat | poi |  |  | en | 0.039299813478170006 |  |  |
| V022:alt_query_he | alt_query_he | רד מיט |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | רד מיט | poi |  |  | he | 0.039299813478170006 |  |  |
| V025:alt_query_he | alt_query_he | פלאפל הזקנים |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | פלאפל הזקנים | poi |  |  | he | 0.030159311709074134 |  |  |
| V027:alt_query_en | alt_query_en | Deli Cream |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | miss | hit | Deli Cream | poi |  |  | en | 5377.858485624829 |  |  |
| V028:alt_query_en | alt_query_en | Mousseline |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | miss | hit | Mousseline | poi |  |  | en | 1694.4458966171424 |  |  |
| V030:alt_query_en | alt_query_en | Barby Club |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Barby Club | poi |  |  | en | 0.024153576946739516 |  |  |
| V032:alt_query_en | alt_query_en | HaArbaa |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | HaArbaa | poi |  |  | en | 0.02188119368919134 |  |  |
| V033:alt_query_en | alt_query_en | MASH |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | MASH | poi |  |  | en | 0.029146508781283303 |  |  |
| V034:alt_query_en | alt_query_en | Rodeo |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Rodeo | poi |  |  | en | 0.030161922789237773 |  |  |
| V038:alt_query_en | alt_query_en | Halev harahav |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Halev harahav | poi |  |  | en | 0.03856265116934941 |  |  |
| V039:alt_query_en | alt_query_en | Landwer |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | miss | hit | Landwer | poi |  |  | en | 20515.93214143505 |  |  |
| V039:alt_query_he | alt_query_he | סמיראמיס |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | סמיראמיס | poi |  |  | he | 0.043492250300266704 |  |  |
| V040:alt_query_en | alt_query_en | Ima |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Ima | poi |  |  | en | 0.029187625172965543 |  |  |
| V040:alt_query_he | alt_query_he | אמא |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | אמא | poi |  |  | he | 0.029187625172965543 |  |  |
| V041:alt_query_en | alt_query_en | Americana Hotel Restaurant |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Americana Hotel Restaurant | poi |  |  | en | 0.022238985558309388 |  |  |
| V046:alt_query_he | alt_query_he | אואזיס |  | he | hebrew | venue | success | haversine_within_original_tolerance | hit | hit | אואזיס | poi |  |  | he | 0.052701552528252524 |  |  |
| V048:alt_query_en | alt_query_en | Al Reda |  | en | latin_or_source_label | venue | success | haversine_within_original_tolerance | hit | hit | Al Reda | poi |  |  | en | 0.058130007606391566 |  |  |
| GTFS-TRANS-13583-en | accepted-gtfs-translation | Dizengoff Center/Dizengoff | Dizengoff Center/Dizengoff | en | latin | translated_stop | success | exact_stop_reference | miss | miss | Dizengoff Center/Dizengoff | stop |  |  | en | 54.00054617208838 |  |  |
| GTFS-TRANS-42658-en | accepted-gtfs-translation | Naomi Shemer Blvd/Hatane Pras Israel | Naomi Shemer Blvd/Hatane Pras Israel | en | latin | translated_stop | success | exact_stop_reference | miss | miss | Naomi Shemer Blvd/Hatane Pras Israel | stop |  |  | en | 0.0 |  |  |
| OSM-ADDR-HE-001 | explicit-osm-language-tag | י.ל. גורדון 24 תל אביב | י.ל. גורדון | he | hebrew | address | success | haversine_within_original_tolerance | hit | hit | י.ל. גורדון 24, Tel Aviv | address | house_number | address_node | he | 0.0 |  |  |
| OSM-ADDR-EN-001 | explicit-osm-language-tag | 113 Ben Yehuda, Tel Aviv | Ben Yehuda | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Ben Yehuda 113, תל־אביב–יפו | address | house_number | address_node | en | 1.018171141763118 |  |  |
| OSM-ADDR-EN-002 | explicit-osm-language-tag | 3 Arlosoroff | Arlosoroff | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Arlosoroff 3, קרית שמונה | address | house_number | address_node | en | 0.0 |  |  |
| OSM-ADDR-EN-003 | explicit-osm-language-tag | 3 Azar | Azar | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Azar 3, חיפה | address | house_number | address_node | en | 0.0 |  |  |
| OSM-ADDR-EN-004 | explicit-osm-language-tag | 2 Technology Park Malha | Technology Park Malha | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Technology Park Malha 2, ירושלים | address | house_number | address_node | en | 0.0 |  |  |
| OSM-ADDR-EN-005 | explicit-osm-language-tag | 3 HaMelacha | HaMelacha | en | latin | address | success | haversine_within_original_tolerance | hit | hit | HaMelacha 3, נתניה | address | house_number | address_node | en | 0.0 |  |  |
| OSM-ADDR-EN-006 | explicit-osm-language-tag | 5 Nahal Gila | Nahal Gila | en | latin | address | success | haversine_within_original_tolerance | hit | hit | Nahal Gila 5, בית שמש | address | house_number | address_node | en | 0.0 |  |  |
