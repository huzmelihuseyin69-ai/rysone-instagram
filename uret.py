"""İçerik JSON'undaki her gönderiyi şablona yerleştirip PNG üretir ve taşma denetler.
kullanım: python3 uret.py icerik/gonderiler.json [id ...]          -> cikti/<id>.png          (hikâye 1080x1920)
          python3 uret.py --gonderi icerik/akis.json [id ...]      -> cikti_gonderi/<id>.png  (gönderi 1080x1350)"""
import html, json, math, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KOK = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VARSAYILAN = {"durum": "çevrimiçi", "site": "rysone.ai", "buton": "HEMEN DENE", "etiket": "#rysone.ai", "soru_boyut": "150px"}

# gönderi: aynı şablonlar 1256x1570 CSS px'te dizilir, 0.86 ölçekle 1080x1350 çekilir
BICIMLER = {
    "hikaye": {"pencere": "1080,1920", "olcek": "1", "klasor": "cikti", "css": ""},
    "gonderi": {"pencere": "1256,1570", "olcek": "0.86", "klasor": "cikti_gonderi",
                "css": "<style>html,body{width:1256px;height:1570px}body{padding:120px 120px 110px}"
                       ".ust,.wrap{margin-top:auto!important}</style>"},
}
BICIM = BICIMLER["hikaye"]

# body iç boşluğu (güvenli alan) dışına çıkan öğeleri sayfa başlığına yazar (.deco/.glow süs öğeleri hariç)
DENETIM = """<script>document.fonts.ready.then(()=>{const c=getComputedStyle(document.body),W=document.body.offsetWidth,H=document.body.offsetHeight,
L=parseFloat(c.paddingLeft)-2,R=W-parseFloat(c.paddingRight)+2,T=parseFloat(c.paddingTop)-2,B=H-parseFloat(c.paddingBottom)+2,k=[];
document.querySelectorAll('body *').forEach(e=>{if(e.closest('.deco,.glow,script,style'))return;
const r=e.getBoundingClientRect();if(!r.width||!r.height)return;
if(r.left<L||r.right>R||r.top<T||r.bottom>B)k.push((e.className||e.tagName)+'@'+[r.left,r.top,r.right,r.bottom].map(Math.round))});
document.title='DENETIM:'+(k.length?k.slice(0,4).join(' | '):'OK')})</script>"""

def metin(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")

def dalgalar(n=26):
    out = []
    for i in range(n):
        amp, faz, y0 = 70 + i * 4, i * 0.22, 420 + i * 14
        pts = " ".join(f"{x},{y0 + amp * math.sin(x / 210 + faz) + 40 * math.sin(x / 90 + faz * 2):.1f}" for x in range(0, 1301, 20))
        out.append(f'<polyline points="{pts}" stroke="rgba(255,255,255,{0.12 + 0.02 * (i % 5):.2f})" stroke-width="2"/>')
    return "".join(out)

LISTE = {
    "mesajlar": lambda l: "".join(f'<div class="m {m["kim"]}">{metin(m["metin"])}<small>{html.escape(m.get("saat", ""))}</small></div>' for m in l),
    "bildirimler": lambda l: "".join(
        f'<div class="n"><div class="ic">R</div><div class="nb"><div class="row"><span>RYSONE</span><span>{html.escape(n["zaman"])}</span></div>'
        f'<b>{metin(n["baslik"])}</b><p>{metin(n["metin"])}</p></div></div>' for n in l),
    "adimlar": lambda l: "".join(f'<div class="s"><div class="num">{i}</div><div><b>{metin(a["baslik"])}</b><p>{metin(a["metin"])}</p></div></div>'
                                 for i, a in enumerate(l, 1)),
    "sol_maddeler": lambda l: "".join(f"<li><span>{metin(x)}</span></li>" for x in l),
    "sag_maddeler": lambda l: "".join(f"<li><span>{metin(x)}</span></li>" for x in l),
    "etiketler": lambda l: "".join(f"<li>{metin(x)}</li>" for x in l),
}

def doldur(g):
    sablon = (KOK / "sablonlar" / f'{g["sablon"]}.html').read_text(encoding="utf-8")
    veri = {**VARSAYILAN, **g}
    if not veri["buton"]: sablon = sablon.replace('<div class="btn">{{buton}} &nbsp;→</div>', "")
    alanlar = {k: metin(v) for k, v in veri.items() if isinstance(v, str)}
    alanlar.update({k: f(veri[k]) for k, f in LISTE.items() if k in veri})
    alanlar["dalgalar"] = dalgalar()
    alanlar["logo"] = "logo_navy" if veri["tema"] == "acik" else "logo_white"
    eksik = set(re.findall(r"\{\{(\w+)\}\}", sablon)) - alanlar.keys()
    if eksik: raise ValueError(f'{g["id"]}: eksik alan(lar): {", ".join(sorted(eksik))}')
    return re.sub(r"\{\{(\w+)\}\}", lambda m: alanlar[m.group(1)], sablon).replace("</head>", BICIM["css"] + "</head>").replace("</body>", DENETIM + "</body>")

def chrome(*args):
    return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--force-device-scale-factor={BICIM['olcek']}",
                           f"--window-size={BICIM['pencere']}", "--virtual-time-budget=8000", *args], capture_output=True, text=True, check=True)

def ciz(g):
    cikti = KOK / BICIM["klasor"]
    gecici = cikti / f'_{g["id"]}.html'
    gecici.write_text(doldur(g), encoding="utf-8")
    try:
        dom = chrome("--dump-dom", gecici.as_uri()).stdout
        denetim = re.search(r"<title>(.*?)</title>", dom, re.S)
        denetim = html.unescape(denetim.group(1)) if denetim else "DENETIM:sonuç yok"
        chrome(f"--screenshot={cikti / (g['id'] + '.png')}", gecici.as_uri())
    finally:
        gecici.unlink()
    return g["id"], denetim

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[0] == "--gonderi": BICIM = BICIMLER["gonderi"]; args = args[1:]
    gonderiler = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    secili = set(args[1:])
    if secili: gonderiler = [g for g in gonderiler if g["id"] in secili]
    (KOK / BICIM["klasor"]).mkdir(exist_ok=True)
    sorunlu = 0
    with ThreadPoolExecutor(4) as ex:
        for gid, d in ex.map(ciz, gonderiler):
            ok = d == "DENETIM:OK"; sorunlu += not ok
            print(("✓ " if ok else "✗ ") + gid + ("" if ok else "  " + d))
    print(f"{len(gonderiler)} görsel, {sorunlu} sorunlu")
