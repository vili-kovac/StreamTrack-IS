from flask import Flask, request, make_response, jsonify, render_template
from pony import orm  # biblioteka za rad s bazom podataka
from datetime import datetime
import json

db = orm.Database()  # baza podataka
app = Flask(__name__)  # poziv konstruktora flask biblioteke

# prva (glavna) tablica
class Pjesma(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    naslov = orm.Required(str)
    izvodac = orm.Required(str)
    metrike = orm.Set("Metrika")


# druga tablica - podaci o streamovima
class Metrika(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    platforma = orm.Required(str)
    broj_streamova = orm.Required(int)
    zarada_po_streamu = orm.Required(float)
    datum_izmjene = orm.Required(datetime)
    pjesma = orm.Required("Pjesma")


# konfiguracija baze podataka
db.bind(provider="sqlite", filename="database.sqlite", create_db=True)  # kreiranje baze
db.generate_mapping(create_tables=True)  # kreiranje tablica


# pomocna funkcija za datum - pretvaranje datuma iz forme ili JSON-a u datetime objekt
def procitaj_datum(datum):
    try:
        return datetime.fromisoformat(datum)
    except Exception:
        return datetime.now()


# funkcija za dodavanje zapisa u tablicu metrike
def dodaj_metriku(pjesma, podaci):
    Metrika(
        platforma=podaci["platforma"],
        broj_streamova=int(podaci["broj_streamova"]),
        zarada_po_streamu=float(podaci["zarada_po_streamu"]),
        datum_izmjene=procitaj_datum(podaci.get("datum_izmjene")),
        pjesma=pjesma
    )


# funkcija za dobivanje zadnjeg zapisa po pojedinoj streaming platformi
def zadnje_po_platformi(metrike):
    zadnji_zapis = {}

    for m in metrike:
        if m.platforma not in zadnji_zapis:
            zadnji_zapis[m.platforma] = m
        elif m.datum_izmjene > zadnji_zapis[m.platforma].datum_izmjene:
            zadnji_zapis[m.platforma] = m

    return zadnji_zapis


# priprema pjesme za prikaz u tablici
def pripremi_pjesmu(pjesma, metrike):
    zadnji = zadnje_po_platformi(metrike)
    platforme = []
    ukupno_streamova = 0
    ukupna_zarada = 0

    for platforma in zadnji:
        m = zadnji[platforma]
        ukupno_streamova += m.broj_streamova
        ukupna_zarada += m.broj_streamova * m.zarada_po_streamu
        tekst = platforma + ": " + str(m.broj_streamova)  # prikazuje broj streamova za posljedni datum unosa
        tekst += " (" + m.datum_izmjene.strftime("%d.%m.%Y.") + ")"  # posljednji datum unosa
        platforme.append(tekst)

    return {
        "id": pjesma.id,
        "naslov": pjesma.naslov,
        "izvodac": pjesma.izvodac,
        "platforme": platforme,
        "ukupno_streamova": ukupno_streamova,
        "ukupna_zarada": round(ukupna_zarada, 2),
        "viralnost": "🔥 VIRALNO" if ukupno_streamova > 1000000 else ""  # ako je pjesma skupila vise od 1000000 smatramo je viralnom
    }


# izbornici u filterima
def get_filtere():
    platforme = []
    godine = []
    mjeseci = []

    with orm.db_session:
        for m in Metrika.select():
            if m.platforma not in platforme:
                platforme.append(m.platforma)
            if m.datum_izmjene.year not in godine:
                godine.append(m.datum_izmjene.year)
            if m.datum_izmjene.month not in mjeseci:
                mjeseci.append(m.datum_izmjene.month)

    platforme.sort()
    godine.sort()
    mjeseci.sort()

    return {
        "platforme": platforme,
        "godine": godine,
        "mjeseci": mjeseci
    }


# funkcija granice za povijesni filter
def granica_filtera(godina, mjesec):
    if not godina:
        return None

    godina = int(godina)  # moramo pretvoriti string u int

    if not mjesec:
        return datetime(godina + 1, 1, 1)  # ako nije odabran mjesec vec cijela godina uzima se 1.1. sljedece godine

    mjesec = int(mjesec)

    if mjesec == 12:
        return datetime(godina + 1, 1, 1)  # jer ako je mjesec prosinac gornja granica mora biti sjecanj sljedece godine

    return datetime(godina, mjesec + 1, 1)


# route za dodavanje nove pjesme
@app.route("/dodaj/pjesmu", methods=["POST", "GET"])
def dodaj_pjesmu():
    if request.method == "GET":
        return make_response(render_template("dodaj_pjesmu.html"), 200)

    try:
        podaci = dict(request.form)

        with orm.db_session:
            pjesma = Pjesma(
                naslov=podaci["naslov"],
                izvodac=podaci["izvodac"]
            )

            dodaj_metriku(pjesma, podaci)

        return make_response(render_template("dodaj_pjesmu.html", poruka="Pjesma je spremljena."), 200)

    except Exception as e:
        return make_response(render_template("dodaj_pjesmu.html", greska=str(e)), 200)

# route za prikaz pjesama, filtere i sortiranje
@app.route("/vrati/pjesme", methods=["GET"])
def vrati_pjesme():
    q_original = request.args.get("q", "")  # originalni tekst pretrage za prikaz u formi
    q = q_original.lower()  # mala slova zbog za usporedbe kod pretrage

    platforma = request.args.get("platforma", "")
    godina = request.args.get("godina", "")
    mjesec = request.args.get("mjesec", "")
    sortiranje = request.args.get("sort", "")

    granica = granica_filtera(godina, mjesec)
    data = []

    # pamtimo sto je korisnik odabrao u filterima i saljemo natrag u HTML da se odabrani filteri ne resetiraju
    odabrano = {
        "q": q_original,
        "platforma": platforma,
        "godina": godina,
        "mjesec": mjesec,
        "sort": sortiranje
    }

    try:
        with orm.db_session:
            for pjesma in Pjesma.select():
                if q and q not in (pjesma.naslov + " " + pjesma.izvodac).lower():
                    continue

                metrike = []

                for m in pjesma.metrike:
                    if platforma and m.platforma != platforma:
                        continue
                    if granica and m.datum_izmjene >= granica:
                        continue

                    metrike.append(m)

                if (platforma or granica) and len(metrike) == 0:
                    continue

                data.append(pripremi_pjesmu(pjesma, metrike))

            if sortiranje == "streamovi":
                data.sort(key=lambda x: x["ukupno_streamova"], reverse=True)
            if sortiranje == "zarada":
                data.sort(key=lambda x: x["ukupna_zarada"], reverse=True)
            if sortiranje == "naslov":
                data.sort(key=lambda x: x["naslov"])

        return make_response(render_template(
            "popis_pjesama.html",
            data=data,
            filteri=get_filtere(),
            odabrano=odabrano
        ), 200)

    except Exception as e:
        return make_response(render_template(
            "popis_pjesama.html",
            data=[],
            filteri=get_filtere(),
            odabrano=odabrano,
            greska=str(e)
        ), 200)
        
        
# funkcije za vizualizacije
# top 5 pjesama i zarada po platformi
def get_top_pjesme_i_zarada():
    top_pjesme = []
    zarada_po_platformi = {}

    with orm.db_session:
        for pjesma in Pjesma.select():
            podaci_pjesme = pripremi_pjesmu(pjesma, pjesma.metrike)
            zadnje = zadnje_po_platformi(pjesma.metrike)

            top_pjesme.append({
                "naslov": podaci_pjesme["naslov"],
                "streamovi": podaci_pjesme["ukupno_streamova"]
            })

            for platforma in zadnje:
                m = zadnje[platforma]
                if m.platforma not in zarada_po_platformi:
                    zarada_po_platformi[m.platforma] = 0
                zarada_po_platformi[m.platforma] += m.broj_streamova * m.zarada_po_streamu

    top_pjesme.sort(key=lambda x: x["streamovi"], reverse=True)
    return top_pjesme[:5], zarada_po_platformi


# streamovi kroz vrijeme
def get_streamovi_kroz_vrijeme():
    streamovi_po_vremenu = {}
    zadnje_stanje = {}

    with orm.db_session:
        metrike = Metrika.select()[:]
        metrike.sort(key=lambda m: m.datum_izmjene)

        for m in metrike:
            mjesec = m.datum_izmjene.strftime("%Y-%m")
            kljuc = str(m.pjesma.id) + "-" + m.platforma
            zadnje_stanje[kljuc] = m

            ukupno = 0
            for zapis in zadnje_stanje.values():
                ukupno += zapis.broj_streamova

            streamovi_po_vremenu[mjesec] = ukupno

    return streamovi_po_vremenu


# route za vizualizaciju
@app.route("/vrati/pjesme/vizualizacija", methods=["GET"])
def vizualizacija():
    try:
        # poziv pomocnih funkcija
        top_pjesme, zarada_po_platformi = get_top_pjesme_i_zarada()
        streamovi_po_vremenu = get_streamovi_kroz_vrijeme()

        # priprema za HTML
        top_labels = [p["naslov"] for p in top_pjesme]
        top_values = [p["streamovi"] for p in top_pjesme]

        platforme_labels = list(zarada_po_platformi.keys())
        platforme_values = [round(zarada_po_platformi[p], 2) for p in platforme_labels]

        vrijeme_labels = sorted(list(streamovi_po_vremenu.keys()))
        vrijeme_values = [streamovi_po_vremenu[v] for v in vrijeme_labels]

    except Exception:
        # ako je baza prazna, saljemo prazne liste da se stranica ne srusi
        top_labels, top_values = [], []
        platforme_labels, platforme_values = [], []
        vrijeme_labels, vrijeme_values = [], []

    return make_response(render_template(
        "vizualizacija.html",
        top_labels=top_labels,
        top_values=top_values,
        platforme_labels=platforme_labels,
        platforme_values=platforme_values,
        vrijeme_labels=vrijeme_labels,
        vrijeme_values=vrijeme_values
    ), 200)


# route za izmjenu pjesme i dodavanje novog zapisa metrike
@app.route("/pjesma/<int:pjesma_id>", methods=["PATCH"])
def izmjeni_pjesmu(pjesma_id):
    try:
        podaci = request.json

        with orm.db_session:
            pjesma = Pjesma[pjesma_id]

            if "naslov" in podaci:
                pjesma.naslov = podaci["naslov"]
            if "izvodac" in podaci:
                pjesma.izvodac = podaci["izvodac"]
            if "platforma" in podaci and podaci.get("broj_streamova"):
                dodaj_metriku(pjesma, podaci)

        return make_response(jsonify({"response": "Success"}), 200)

    except Exception as e:
        return make_response(jsonify({"response": "Fail", "error": str(e)}), 400)


# route za brisanje pjesme i svih njezinih metrika
@app.route("/pjesma/<int:pjesma_id>", methods=["DELETE"])
def obrisi_pjesmu(pjesma_id):
    try:
        with orm.db_session:
            pjesma = Pjesma[pjesma_id]

            for m in list(pjesma.metrike):
                m.delete()

            pjesma.delete()

        return make_response(jsonify({"response": "Success"}), 200)

    except Exception as e:
        return make_response(jsonify({"response": "Fail", "error": str(e)}), 400)


# pocetna stranica
@app.route("/", methods=["GET"])
def home():
    return make_response(render_template("index.html"), 200)


# funkcija za ubacivanje podataka
def ubaci_pocetne_podatke():
    with orm.db_session:
        koliko_pjesama_ima = Pjesma.select().count()  # provjeri koliko imamo u bazi

        if koliko_pjesama_ima > 0:
            return

        # citanje JSON datoteke
        datoteka = open("pjesme_data.json", "r", encoding="utf-8")
        pjesme_lista = json.load(datoteka)
        datoteka.close()

        # prolazimo kroz pjesme iz JSON-a jednu po jednu
        for trenutna_pjesma in pjesme_lista:

            # upisujemo novu pjesmu u bazu
            nova_pjesma = Pjesma(
                naslov=trenutna_pjesma["naslov"],
                izvodac=trenutna_pjesma["izvodac"]
            )

            lista_metrika_za_ovu_pjesmu = trenutna_pjesma["metrike"]

            # za tu pjesmu upisujemo sve njezine metrike
            for jedna_metrika in lista_metrika_za_ovu_pjesmu:
                dodaj_metriku(nova_pjesma, jedna_metrika)

        print("Pocetni podaci su uspjesno ubaceni u bazu.")


ubaci_pocetne_podatke()


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0", debug=True)