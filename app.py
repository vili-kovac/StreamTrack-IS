from flask import Flask, request, make_response, jsonify, render_template
from pony import orm  # datoteka za rad s bazom podataka
from datetime import datetime
import json

db = orm.Database()  # baza podataka
app = Flask(__name__)  # poziv konstruktora


# prva tablica - pjesma
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


# konfiguracija baze
db.bind(provider="sqlite", filename="database.sqlite", create_db=True)  # kreiranje baze ako ne postoji
db.generate_mapping(create_tables=True)  # kreiranje tablica


# pomocna funkcija za datum
def procitaj_datum(datum):
    try:
        return datetime.fromisoformat(datum)
    except Exception:
        return datetime.now()


# dodavanje jednog zapisa metrike
def dodaj_metriku(pjesma, podaci):
    Metrika(
        platforma=podaci["platforma"],
        broj_streamova=int(podaci["broj_streamova"]),
        zarada_po_streamu=float(podaci["zarada_po_streamu"]),
        datum_izmjene=procitaj_datum(podaci.get("datum_izmjene")),
        pjesma=pjesma
    )


# povijesni model - zadnji zapis po platformi
def zadnje_po_platformi(metrike):
    zadnje = {}

    for m in metrike:
        if m.platforma not in zadnje:
            zadnje[m.platforma] = m
        elif m.datum_izmjene > zadnje[m.platforma].datum_izmjene:
            zadnje[m.platforma] = m

    return zadnje


# priprema jedne pjesme za prikaz u tablici
def slozi_pjesmu(pjesma, metrike):
    zadnje = zadnje_po_platformi(metrike)
    platforme = []
    ukupno_streamova = 0
    ukupna_zarada = 0

    for platforma in zadnje:
        m = zadnje[platforma]
        ukupno_streamova += m.broj_streamova
        ukupna_zarada += m.broj_streamova * m.zarada_po_streamu
        tekst = platforma + ": " + str(m.broj_streamova)
        tekst += " (" + m.datum_izmjene.strftime("%d.%m.%Y.") + ")"
        platforme.append(tekst)

    return {
        "id": pjesma.id,
        "naslov": pjesma.naslov,
        "izvodac": pjesma.izvodac,
        "platforme": platforme,
        "ukupno_streamova": ukupno_streamova,
        "ukupna_zarada": round(ukupna_zarada, 2),
        "viralnost": "🔥 VIRALNO" if ukupno_streamova > 1000000 else ""
    }


# podaci za padajuce izbornike u filterima
def get_filtere():
    platforme = []
    godine = []
    mjeseci = []

    with orm.db_session:
        for m in orm.select(m for m in Metrika):
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


# granica za povijesni filter
def granica_filtera(godina, mjesec):
    if not godina:
        return None

    godina = int(godina)

    if not mjesec:
        return datetime(godina + 1, 1, 1)

    mjesec = int(mjesec)

    if mjesec == 12:
        return datetime(godina + 1, 1, 1)

    return datetime(godina, mjesec + 1, 1)


# ruta za dodavanje nove pjesme
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


# ruta za prikaz pjesama, filtere i sortiranje
@app.route("/vrati/pjesme", methods=["GET"])
def vrati_pjesme():
    q = request.args.get("q", "").lower()
    platforma = request.args.get("platforma", "")
    godina = request.args.get("godina", "")
    mjesec = request.args.get("mjesec", "")
    sortiranje = request.args.get("sort", "")
    granica = granica_filtera(godina, mjesec)
    data = []

    try:
        with orm.db_session:
            for pjesma in orm.select(p for p in Pjesma)[:]:
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

                data.append(slozi_pjesmu(pjesma, metrike))

            if sortiranje == "streamovi":
                data.sort(key=lambda x: x["ukupno_streamova"], reverse=True)
            if sortiranje == "zarada":
                data.sort(key=lambda x: x["ukupna_zarada"], reverse=True)
            if sortiranje == "naslov":
                data.sort(key=lambda x: x["naslov"])

        return make_response(render_template("popis_pjesama.html", data=data, filteri=get_filtere()), 200)

    except Exception as e:
        return make_response(render_template("popis_pjesama.html", data=[], filteri=get_filtere(), greska=str(e)), 200)


# ruta za vizualizaciju grafova
@app.route("/vrati/pjesme/vizualizacija", methods=["GET"])
def vizualizacija():
    top_pjesme = []
    zarada_po_platformi = {}
    streamovi_po_vremenu = {}

    try:
        with orm.db_session:
            # prvi graf - top 5 pjesama po istom izracunu kao u tablici
            for pjesma in orm.select(p for p in Pjesma)[:]:
                podaci_pjesme = slozi_pjesmu(pjesma, pjesma.metrike)
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

            # treci graf - stanje streamova kroz vrijeme
            zadnje_stanje = {}
            metrike = orm.select(m for m in Metrika)[:]
            metrike.sort(key=lambda m: m.datum_izmjene)

            for m in metrike:
                mjesec = m.datum_izmjene.strftime("%Y-%m")
                kljuc = str(m.pjesma.id) + "-" + m.platforma
                zadnje_stanje[kljuc] = m
                streamovi_po_vremenu[mjesec] = sum(x.broj_streamova for x in zadnje_stanje.values())

        top_pjesme.sort(key=lambda x: x["streamovi"], reverse=True)
        top_pjesme = top_pjesme[:5]

        platforme_labels = list(zarada_po_platformi.keys())
        platforme_values = []
        vrijeme_labels = list(streamovi_po_vremenu.keys())
        vrijeme_values = []

        vrijeme_labels.sort()

        # drugi graf - zarada po platformama
        for p in platforme_labels:
            platforme_values.append(round(zarada_po_platformi[p], 2))

        for v in vrijeme_labels:
            vrijeme_values.append(streamovi_po_vremenu[v])

    except Exception:
        top_pjesme = []
        platforme_labels = []
        platforme_values = []
        vrijeme_labels = []
        vrijeme_values = []

    return make_response(render_template(
        "vizualizacija.html",
        top_labels=[p["naslov"] for p in top_pjesme],
        top_values=[p["streamovi"] for p in top_pjesme],
        platforme_labels=platforme_labels,
        platforme_values=platforme_values,
        vrijeme_labels=vrijeme_labels,
        vrijeme_values=vrijeme_values
    ), 200)


# ruta za izmjenu pjesme i dodavanje novog zapisa metrike
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


# ruta za brisanje pjesme i svih njezinih metrika
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


# pocetni podaci iz JSON datoteke
@orm.db_session
def ubaci_pocetne_podatke():
    if orm.select(p for p in Pjesma).count() > 0:
        return

    with open("pjesme_data.json", "r", encoding="utf-8") as f:
        pjesme_lista = json.load(f)

    for p_data in pjesme_lista:
        pjesma = Pjesma(
            naslov=p_data["naslov"],
            izvodac=p_data["izvodac"]
        )

        for m_data in p_data["metrike"]:
            dodaj_metriku(pjesma, m_data)

    orm.commit()
    print("Pocetni podaci iz JSON-a su ubaceni u bazu.")


ubaci_pocetne_podatke()


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0", debug=True)