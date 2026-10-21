"""Sıradaki görseli Instagram'da paylaşır, durum.json'u günceller.
kullanım: python paylas.py hikaye|gonderi

Ortam değişkenleri:
  IG_USER_ID, IG_ACCESS_TOKEN   (GitHub Secrets)
  GORSEL_TABAN_URL              yayin/ klasörünün herkese açık adresi
  BITINCE                       "dur" (varsayılan) ya da "basa_don"
  ZORLA                         "1" ise bugün paylaşılmış olsa da paylaşır
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KOK = Path(__file__).parent
DURUM = KOK / "durum.json"
API_SURUM = os.environ.get("GRAPH_SURUM", "v23.0")
ETIKETLER = "#rysone #yapayzeka #randevu #işletme #müşterihizmetleri #dijitalasistan #küçükişletme"


def api_tabani(token):
    # Instagram Login token'ları "IG" ile başlar, Facebook Login token'ları "EA" ile
    host = "graph.instagram.com" if token.startswith("IG") else "graph.facebook.com"
    return f"https://{host}/{API_SURUM}"


def istek(yontem, url, **kw):
    r = requests.request(yontem, url, timeout=60, **kw)
    if r.status_code >= 400:
        sys.exit(f"API hatası {r.status_code}: {r.text}")
    return r.json()


def aciklama(ad):
    kayitlar = json.loads((KOK / "icerik" / "akis.json").read_text(encoding="utf-8"))
    metin = next(k["aciklama"] for k in kayitlar if k["id"] == Path(ad).stem)
    return f"{metin}\n\n{ETIKETLER}"


def main():
    tur = sys.argv[1]
    if tur not in ("hikaye", "gonderi"):
        sys.exit("kullanım: python paylas.py hikaye|gonderi")
    ig_id = os.environ["IG_USER_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]
    taban_url = os.environ["GORSEL_TABAN_URL"].rstrip("/")
    bitince = os.environ.get("BITINCE", "dur")
    zorla = os.environ.get("ZORLA") == "1"

    gorseller = sorted(p.name for p in (KOK / "yayin" / tur).glob("*.jpg"))
    tum_durum = json.loads(DURUM.read_text()) if DURUM.exists() else {}
    durum = tum_durum.get(tur, {"siradaki": 0})
    bugun = datetime.now(timezone(timedelta(hours=3))).date().isoformat()

    if durum.get("son_tarih") == bugun and not zorla:
        print(f"{tur}: bugün zaten paylaşıldı, atlanıyor.")
        return

    i = durum["siradaki"]
    if i >= len(gorseller):
        if bitince != "basa_don":
            print(f"{tur}: {len(gorseller)} görsel bitti, paylaşım durdu.")
            return
        i = 0

    ad = gorseller[i]
    url = f"{taban_url}/{tur}/{ad}"
    taban = api_tabani(token)
    print(f"{tur} paylaşılıyor ({i + 1}/{len(gorseller)}): {url}")

    veri = {"image_url": url, "access_token": token}
    if tur == "hikaye":
        veri["media_type"] = "STORIES"
    else:
        veri["caption"] = aciklama(ad)
    kap_id = istek("POST", f"{taban}/{ig_id}/media", data=veri)["id"]

    for _ in range(30):
        s = istek("GET", f"{taban}/{kap_id}",
                  params={"fields": "status_code", "access_token": token})
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            sys.exit(f"Kapsayıcı hatası: {s}")
        time.sleep(5)
    else:
        sys.exit("Kapsayıcı 150 sn içinde hazır olmadı.")

    yayin = istek("POST", f"{taban}/{ig_id}/media_publish",
                  data={"creation_id": kap_id, "access_token": token})
    print(f"Paylaşıldı, medya id: {yayin['id']}")

    tum_durum[tur] = {"siradaki": i + 1, "son_tarih": bugun, "son_gorsel": ad, "son_medya_id": yayin["id"]}
    DURUM.write_text(json.dumps(tum_durum, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
