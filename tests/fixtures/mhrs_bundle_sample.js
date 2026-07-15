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

// --- API OLMAYAN: Draft.js CSS classname'leri (yanlış pozitif tuzağı) ---
var c={block:"public/DraftStyleDefault/block",ltr:"public/DraftStyleDefault/ltr"};
// --- API OLMAYAN: Map/Set operasyonları (.get/.delete ama axios değil) ---
n.delete(e.pointerId); m.get(t.key); q.delete(r.id);
}();
