from flask import Flask 
from pony import orm # datoteka xa rad s bazom podataka 
from datetime import datetime 


db = orm.Database() # baza podataka 

app = Flask(__name__) # poziv konstruktora 


# prva tablica 
class Pjesma(db.Entity):
    id = orm.PrimaryKey(int, auto = True)
    naslov = orm.Required(str)
    izvodac = orm.Required(str)
    datum_izrade = orm.Required(datetime)
    godina = orm.Required(int)
    metrike = orm.Set('Metrika')

# druga tablica 

class Metrika(db.Entity):
    id = orm.PrimaryKey(int, auto = True)
    platforma = orm.Required(str)
    broj_streamova = orm.Required(int)
    zarada_po_streamu = orm.Required(float)
    datum_izmjene = orm.Required(datetime)
    pjesma = orm.Required('Pjesma')

# konfiguracija baze 

db.bind(provider="sqlite", filename="database.sqlite", create_db=True) # kreiranje baze koja se stvara ako ne postoji 
db.generate_mapping(create_tables=True) # kreiranje tablica 



# pocetni podaci 

@orm.db_session # otvaramo bazu 
def ubaci_pocetne_podatke():
    # Prvo provjeravamo je li tablica Pjesma potpuno prazna
    if orm.select(p for p in Pjesma).count() == 0:
        
        # 1. Stvaramo prvu pjesmu (Pjesma A) i spremamo je u varijablu 'p1'
        p1 = Pjesma(
            naslov="Thinkig Of You", 
            izvodjac="Teddy Swims", 
            datum_izrade=datetime.now(), 
            godina=2024
        )
        
        # 2. Stvaramo drugu pjesmu (Pjesma B) i spremamo je u varijablu 'p2'
        p2 = Pjesma(
            naslov="Love You Not", 
            izvodjac="Sabrina Carpenter", 
            datum_izrade=datetime.now(), 
            godina=2026
        )
        
        # 3. Sada dodajemo podatke o slušanosti (Metrike) i spajamo ih na te pjesme
        orm.Metrika(
            platforma="Spotify", 
            broj_streamova=1200000, 
            zarada_po_streamu=0.004, 
            datum_izmjene=datetime.now(), 
            pjesma=p1  # Kažemo bazi: Ovi streamovi pripadaju Pjesmi A
        )
        
        orm.Metrika(
            platforma="YouTube", 
            broj_streamova=500000, 
            zarada_po_streamu=0.001, 
            datum_izmjene=datetime.now(), 
            pjesma=p1  # Ovi streamovi isto pripadaju Pjesmi A
        )
        
        orm.Metrika(
            platforma="Spotify", 
            broj_streamova=80000, 
            zarada_po_streamu=0.004, 
            datum_izmjene=datetime.now(), 
            pjesma=p2  # Ovi streamovi pripadaju Pjesmi B
        )
        
        orm.commit() # Ova naredba zaključava i trajno sprema ove podatke u datoteku
        print("Početni podaci su uspješno spremljeni u bazu!")

# Na kraju, moramo stvarno i pozvati ovu funkciju da se ona izvrši!
ubaci_pocetne_podatke()