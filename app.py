from flask import Flask,request,make_response,jsonify, render_template
from pony import orm
from datetime import datetime
import json

DB = orm.Database()
app = Flask(__name__)

# tablica pjesama
class Pjesma(DB.Entity):
    id = orm.PrimaryKey(int, auto=True)
    naslov = orm.Required(str)
    izvodac = orm.Required(str)
    godina = orm.Required(int)
    datum_izrade = orm.Required(datetime)
    metrike = orm.Set("Metrika")

# zapisi streamova po platformi i datumu
class Metrika(DB.Entity):
    id = orm.PrimaryKey(int, auto=True)
    platforma = orm.Required(str)
    broj_streamova = orm.Required(int)
    zarada_po_streamu = orm.Required(float)
    datum_izmjene = orm.Required(datetime)
    pjesma = orm.Required(Pjesma)

# spajanje baze
DB.bind(provider="sqlite", filename="database.sqlite", create_db=True)
DB.generate_mapping(create_tables=True)


def procitaj_datum(datum, godina=None, mjesec=1):
    try:
        return datetime.fromisoformat(datum)
    except:
        if godina:
            return datetime(int(godina), int(mjesec), 1)
        return datetime.now()


def dodaj_metriku(pjesma, podaci, godina):
    Metrika(
        platforma=podaci["platforma"],
        broj_streamova=int(podaci["broj_streamova"]),
        zarada_po_streamu=float(podaci["zarada_po_streamu"]),
        datum_izmjene=procitaj_datum(podaci.get("datum_izmjene"), godina),
        pjesma=pjesma
    )
def slozi_pjesmu(pjesma, metrike):
    ukupno_streamova = 0
    ukupna_zarada = 0
    platforme = {}

    for m in metrike:
        ukupno_streamova += m.broj_streamova
        ukupna_zarada += m.broj_streamova * m.zarada_po_streamu

        if m.platforma not in platforme:
            platforme[m.platforma] = {
                "streamovi": 0,
                "zadnji": m.datum_izmjene
            }

        platforme[m.platforma]["streamovi"] += m.broj_streamova

        if m.datum_izmjene > platforme[m.platforma]["zadnji"]:
            platforme[m.platforma]["zadnji"] = m.datum_izmjene

    prikaz_platformi = []

    for platforma in platforme:
        tekst = platforma + ": " + str(platforme[platforma]["streamovi"])
        tekst += " (" + platforme[platforma]["zadnji"].strftime("%d.%m.%Y.") + ")"
        prikaz_platformi.append(tekst)

    return {
        "id": pjesma.id,
        "naslov": pjesma.naslov,
        "izvodac": pjesma.izvodac,
        "godina": pjesma.godina,
        "platforme": prikaz_platformi,
        "ukupno_streamova": ukupno_streamova,
        "ukupna_zarada": round(ukupna_zarada, 2),
        "viralnost": "🔥 VIRALNO" if ukupno_streamova > 1000000 else ""
    }


def sort_streamovi(pjesma):
    return pjesma["ukupno_streamova"]


def sort_zarada(pjesma):
    return pjesma["ukupna_zarada"]


def sort_naslov(pjesma):
    return pjesma["naslov"]


def sort_godina(pjesma):
    return pjesma["godina"]


def sort_graf(pjesma):
    return pjesma["streamovi"]


def sortiraj_pjesme(lista, sort):
    if sort == "streamovi":
        lista.sort(key=sort_streamovi, reverse=True)
    if sort == "zarada":
        lista.sort(key=sort_zarada, reverse=True)
    if sort == "naslov":
        lista.sort(key=sort_naslov)
    if sort == "godina":
        lista.sort(key=sort_godina, reverse=True)


def add_pjesma(json_request):
    try:
        with orm.db_session:
            godina = int(json_request["godina"])

            nova_pjesma = Pjesma(
                naslov=json_request["naslov"],
                izvodac=json_request.get("izvodac") or json_request.get("izvodjac"),
                godina=godina,
                datum_izrade=procitaj_datum(json_request.get("datum_izrade"), godina)
            )

            dodaj_metriku(nova_pjesma, json_request, godina)

            return {"response": "Success"}

    except Exception as e:
        return {"response": "Fail", "error": str(e)}


def get_pjesme():
    try:
        q = request.args.get("q", "").lower()
        platforma = request.args.get("platforma", "")
        godina = request.args.get("godina", "")
        mjesec = request.args.get("mjesec", "")
        sort = request.args.get("sort", "")

        with orm.db_session:
            results_list = []

            for pjesma in orm.select(p for p in Pjesma)[:]:
                if q and q not in (pjesma.naslov + " " + pjesma.izvodac).lower():
                    continue

                metrike = []

                for m in pjesma.metrike:
                    if platforma and m.platforma != platforma:
                        continue
                    if godina and m.datum_izmjene.year != int(godina):
                        continue
                    if mjesec and m.datum_izmjene.month != int(mjesec):
                        continue
                    metrike.append(m)

                if (platforma or godina or mjesec) and len(metrike) == 0:
                    continue

                results_list.append(slozi_pjesmu(pjesma, metrike))

            sortiraj_pjesme(results_list, sort)

            return {"response": "Success", "data": results_list}

    except Exception as e:
        return {"response": "Fail", "error": str(e)}


def patch_pjesma(pjesma_id, json_request):
    try:
        with orm.db_session:
            pjesma = Pjesma[pjesma_id]

            if "naslov" in json_request:
                pjesma.naslov = json_request["naslov"]
            if "izvodac" in json_request:
                pjesma.izvodac = json_request["izvodac"]
            if "godina" in json_request:
                pjesma.godina = int(json_request["godina"])
            if "datum_izrade" in json_request:
                pjesma.datum_izrade = procitaj_datum(json_request["datum_izrade"], pjesma.godina)

            if "platforma" in json_request and json_request.get("broj_streamova"):

                for m in list(pjesma.metrike):
                    if m.platforma == json_request["platforma"]:
                        m.delete()
                dodaj_metriku(pjesma, json_request, pjesma.godina)

            return {"response": "Success"}

    except Exception as e:
        return {"response": "Fail", "error": str(e)}


def delete_pjesmu(pjesma_id):
    try:
        with orm.db_session:
            pjesma = Pjesma[pjesma_id]

            for m in list(pjesma.metrike):
                m.delete()

            pjesma.delete()

            return {"response": "Success"}

    except Exception as e:
        return {"response": "Fail", "error": str(e)}


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


def get_podaci_za_grafove():
    try:
        with orm.db_session:
            top_pjesme = []
            zarada_po_platformi = {}
            streamovi_po_vremenu = {}

            for p in orm.select(p for p in Pjesma)[:]:
                ukupno = 0

                for m in p.metrike:
                    ukupno += m.broj_streamova

                top_pjesme.append({"naslov": p.naslov, "streamovi": ukupno})

            for m in orm.select(m for m in Metrika)[:]:
                if m.platforma not in zarada_po_platformi:
                    zarada_po_platformi[m.platforma] = 0

                zarada_po_platformi[m.platforma] += m.broj_streamova * m.zarada_po_streamu

                vrijeme = m.datum_izmjene.strftime("%Y-%m")

                if vrijeme not in streamovi_po_vremenu:
                    streamovi_po_vremenu[vrijeme] = 0

                streamovi_po_vremenu[vrijeme] += m.broj_streamova

            top_pjesme.sort(key=sort_graf, reverse=True)
            top_pjesme = top_pjesme[:5]

            vrijeme_lista = list(streamovi_po_vremenu.keys())
            vrijeme_lista.sort()

            platforme_labels = list(zarada_po_platformi.keys())
            platforme_values = []

            for p in platforme_labels:
                platforme_values.append(round(zarada_po_platformi[p], 2))

            vrijeme_values = []

            for v in vrijeme_lista:
                vrijeme_values.append(streamovi_po_vremenu[v])

            return {
                "response": "Success",
                "data": {
                    "top_labels": [p["naslov"] for p in top_pjesme],
                    "top_values": [p["streamovi"] for p in top_pjesme],
                    "platforme_labels": platforme_labels,
                    "platforme_values": platforme_values,
                    "vrijeme_labels": vrijeme_lista,
                    "vrijeme_values": vrijeme_values
                }
            }

    except Exception as e:
        return {"response": "Fail", "error": str(e)}


@app.route("/dodaj/pjesmu", methods=["POST","GET"])
def dodaj_pjesmu():
    if request.method == "GET":
        return make_response(render_template("dodaj_pjesmu.html"),200)

    response = add_pjesma(dict(request.form))

    if response["response"] == "Success":
        return make_response(render_template("dodaj_pjesmu.html", poruka="Pjesma je spremljena."),200)

    return make_response(render_template("dodaj_pjesmu.html", greska=response["error"]),200)


@app.route("/vrati/pjesme", methods=["GET"])
def vrati_pjesme():
    response = get_pjesme()

    if response["response"] == "Success":
        return make_response(render_template("popis_pjesama.html", data=response["data"], filteri=get_filtere()),200)

    return make_response(render_template("popis_pjesama.html", data=[], filteri=get_filtere(), greska=response["error"]),200)


@app.route("/vrati/pjesme/vizualizacija", methods=["GET"])
def vizualizacija():
    response = get_podaci_za_grafove()

    if response["response"] == "Success":
        data = response["data"]
    else:
        data = {
            "top_labels": [],
            "top_values": [],
            "platforme_labels": [],
            "platforme_values": [],
            "vrijeme_labels": [],
            "vrijeme_values": []
        }

    return make_response(render_template(
        "vizualizacija.html",
        top_labels=data["top_labels"],
        top_values=data["top_values"],
        platforme_labels=data["platforme_labels"],
        platforme_values=data["platforme_values"],
        vrijeme_labels=data["vrijeme_labels"],
        vrijeme_values=data["vrijeme_values"]
    ),200)


@app.route("/pjesma/<int:pjesma_id>", methods=["DELETE"])
def obrisi_pjesmu(pjesma_id):
    response = delete_pjesmu(pjesma_id)

    if response["response"] == "Success":
        return make_response(jsonify(response),200)

    return make_response(jsonify(response),400)


@app.route("/pjesma/<int:pjesma_id>", methods=["PATCH"])
def izmjeni_pjesmu(pjesma_id):
    response = patch_pjesma(pjesma_id, request.json)

    if response["response"] == "Success":
        return make_response(jsonify(response),200)

    return make_response(jsonify(response),400)


@app.route("/", methods=["GET"])
def home():
    return make_response(render_template("index.html"),200)


@orm.db_session
def ubaci_pocetne_podatke():
    if orm.select(p for p in Pjesma).count() > 0:
        return

    with open("pjesme_data.json", "r", encoding="utf-8") as f:
        pjesme_lista = json.load(f)

    for p_data in pjesme_lista:
        godina = int(p_data["godina"])

        nova_pjesma = Pjesma(
            naslov=p_data["naslov"],
            izvodac=p_data["izvodac"],
            godina=godina,
            datum_izrade=procitaj_datum(p_data.get("datum_izrade"), godina)
        )

        for m_data in p_data["metrike"]:
            dodaj_metriku(nova_pjesma, m_data, godina)

    orm.commit()
    print("Pocetni podaci iz JSON-a su ubaceni u bazu.")


ubaci_pocetne_podatke()


if __name__ == "__main__":
   app.run(port=8080, host='0.0.0.0', debug=True)