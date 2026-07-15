// SENTETİK — PHI yok. MHRS vatandas-main.js / chunk yapısını taklit eder.
// Gerçek build 2.1.405'ten alınan KALIP'lar; değerler uydurma.
// Minified webpack + axios; değişken adları gerçek build'deki gibi tek harflidir.
!function(e){function t(n){}
// webpack publicPath + lazy chunk yükleyici (gerçek kalıp)
t.p="/vatandas/";
t.e=function(n){return Promise.resolve(t.p+"vatandas-"+({}[n]||n)+"-chunk.js?t=1700000000000")};
Promise.all([t.e(0),t.e(45)]).then(t.bind(null,61));
t.e(19);
// axios interceptor (gerçek kalıp)
var r={baseURL:"https://prd.mhrs.gov.tr/api/",timeout:6e4};
var o={MSRS_UI_API_URL:"https://prd.mhrs.gov.tr/api/",MSRS_UI_DIRECTORY:"/vatandas/"};

// --- OKUMA uçları: düz literal ---
s.a.get("vatandas/dil").then(function(e){return e.data});
s.a.get("vatandas/menu");
x.a.get("kurum/kurum/kurum-klinik/klinik/select-input");
E.a.get("kurum/randevu/yaklasan-randevularim");
E.a.get("kurum/randevu/randevu-gecmisi");

// --- OKUMA: query string literal'in İÇİNDE + .concat parametre ---
x.a.get("kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId=".concat(e));
E.a.get("kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon-klinik?aksiyonId=".concat(e,"&mhrsKlinikId=").concat(a));

// --- OKUMA: ara-parametreli concat zinciri + -1 "hepsi" sentinel'i ---
g.a.get("kurum/kurum/kurum-klinik/il/".concat(e,"/ilce/").concat(a,"/kurum/").concat(l,"/klinik/").concat(t,"/ana-kurum/select-input"));
f.a.get("kurum/kurum/muayene-yeri/ana-kurum/".concat(-1,"/kurum/").concat(e,"/klinik/").concat(a,"/select-input"));

// --- YAZMA: metodla (POST/PUT/DELETE) ---
h.a.post("kurum/randevu/randevu-ekle",a);
h.a.delete("kurum/randevu/slot-kilitleme");
s.a.post("vatandas/enabiz/login",n,{meta:{isLoginRequest:!0}});
p.a.put("vatandas/favori/ekle",e);

// --- YAZMA: GET ile! (bu sınıf olmadan replay randevu alır) ---
v.a.get("kurum/randevu/iptal-et/".concat(e));
v.a.get("kurum/randevu/ayni-hekimden-randevu-al/".concat(e));
v.a.get("kurum/randevu/geri-al/".concat(e));
v.a.get("kurum/randevu/degisikligi-onayla/".concat(e));
v.a.get("kurum/randevu-ozellik/gizle/".concat(e));

// --- OKUMA: altçizgili sabit — "AL" içerir ama yazma DEĞİL ---
b.a.get("yonetim/genel/parametre/degeri/RIS_RANDEVU_AL_ADIMI");
b.a.get("yonetim/genel/parametre/degeri/SLOT_LISTELEME_MAX_GUN_WEB");

// --- `kurum-rss/` prefix'i: gövdeli POST ile OKUMA (slot arama) ---
// Gerçek kaçak. Allowlist `("vatandas/","kurum/","yonetim/")` iken bu iki uç
// eşleşmedi ve rapora HİÇ girmedi — üstelik Faz 2'nin tüm çekirdeği bunlar.
// "kurum-rss" ile "kurum" kardeş prefix'lerdir; biri ötekinin alt kümesi değil.
var E=function(e,t,n){g.a.post("kurum-rss/randevu/slot-sorgulama/arama",e).then((function(e){e.data.success&&t(e.data.data)})).catch((function(e){return n(e)}))};
var P=function(e,t,n,r,o,i){g.a.post("kurum-rss/randevu/slot-sorgulama/slot",e).then((function(t){n(t.data.data)}))};

// --- BAŞTAN SLASH'lı çağrılar: axios aynı baseURL'e çözer, AYNI uçturlar ---
// İkinci gerçek kaçak. Çıkarıcı literalin prefix'le BAŞLAMASINI şart koşuyordu;
// baştan slash'lı 7 uç (`parola-degistir` dahil) haritaya hiç girmedi. Denetçi de
// aynı kör noktayı paylaşıyordu — kör noktayı arayan araç aynı kör noktaya sahipse
// hiçbir şey bulmaz.
h.a.get("/vatandas/hesap-bilgileri/tema-bilgileri").then((function(e){}));
h.a.put("/vatandas/hesap-bilgileri/parola-degistir",e).then((function(e){}));

// --- API OLMAYAN: Draft.js CSS classname'leri (yanlış pozitif tuzağı) ---
var c={block:"public/DraftStyleDefault/block",ltr:"public/DraftStyleDefault/ltr"};
// --- API OLMAYAN: Map/Set operasyonları (.get/.delete ama axios değil) ---
n.delete(e.pointerId); m.get(t.key); q.delete(r.id);
}();
