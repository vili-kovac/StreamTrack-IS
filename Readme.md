# StreamTrack

Aplikacija omogućuje nositelju glazbenih prava praćenje streamova i izračun procijenjenih tantijema za pjesme na različitim streaming platformama.

Tijekom izrade početni model baze je pojednostavljen jer se pokazalo da je za ovu aplikaciju važnije pratiti povijesno stanje streamova po platformama nego čuvati dodatne podatke koji se ne koriste u funkcionalnostima aplikacije. Zbog toga se pjesma sprema samo s osnovnim podacima, dok se svi podaci o streamovima i zaradi spremaju kroz zasebne zapise metrika.

U stvarnom svijetu izračun zarade od streamova je složeniji jer izdavačke kuće, distributeri, tržišta, tip korisničke pretplate i drugi faktori mogu utjecati na konačan iznos tantijema. U ovoj aplikaciji koristi se pojednostavljeni model koji računa procijenjenu zaradu pomoću prosječne zarade po streamu za pojedinu platformu.

## Struktura aplikacije

Na početnoj stranici korisnik može pristupiti glavnim dijelovima aplikacije:

* popisu pjesama
* dodavanju nove pjesme
* vizualizaciji podataka

Aplikacija podržava osnovne CRUD operacije:

```text
CREATE → dodavanje nove pjesme i prvog zapisa streamova
READ   → pregled popisa pjesama, streamova, zarade i grafova
UPDATE → uređivanje naziva/izvođača pjesme i dodavanje novog zapisa streamova
DELETE → brisanje pjesme i svih njezinih zapisa streamova
```

## Model podataka

Aplikacija koristi dvije glavne tablice:

```text
Pjesma
- id
- naslov
- izvodac

Metrika
- id
- platforma
- broj_streamova
- zarada_po_streamu
- datum_izmjene
- pjesma
```

Tablica `Pjesma` sadrži osnovne podatke o pjesmi. Tablica `Metrika` sadrži podatke o streamovima na određenoj platformi na određeni datum.

Streamovi se ne prepisuju, nego se svaki novi unos sprema kao novi zapis s datumom. Na taj način aplikacija može pratiti promjene kroz vrijeme i prikazivati povijesno stanje streamova.

## Dodavanje pjesme

Kod dodavanja nove pjesme korisnik unosi:

* naslov pjesme
* izvođača
* platformu
* broj streamova na dan zapisa
* zaradu po streamu
* datum zapisa streamova

Ako korisnik ne unese datum zapisa streamova, aplikacija automatski koristi današnji datum. Time se sprječava greška kod praznog datuma i omogućuje jednostavniji unos podataka.

Kod greške aplikacija ne prikazuje sirovi JSON odgovor korisniku, nego poruku greške prikazuje unutar HTML stranice.

## Popis pjesama

Popis pjesama prikazuje tablicu sa sljedećim informacijama:

* naslov pjesme
* izvođača
* streamove po platformama
* ukupan broj streamova
* procijenjenu zaradu
* status pjesme
* akcije za uređivanje i brisanje

Ukupni broj streamova računa se tako da se za svaku platformu uzima zadnje poznato stanje streamova. Ako pjesma prijeđe ukupno 1 000 000 streamova, dobiva status `VIRALNO`.

Kod uređivanja pjesme moguće je promijeniti naslov i izvođača, ali unos novog broja streamova ne briše stare podatke. Novi broj streamova sprema se kao novo povijesno stanje za odabranu platformu i datum.

## Filteri

Popis pjesama podržava pretraživanje i filtriranje po:

* naslovu ili izvođaču
* platformi
* godini zapisa streamova
* mjesecu zapisa streamova

Filter godine i mjeseca ne prikazuje samo zapise unesene točno u tom mjesecu, nego prikazuje zadnje poznato stanje streamova do odabranog perioda.

Na primjer, ako pjesma ima zapis u siječnju i ožujku, a korisnik filtrira veljaču, prikazat će se stanje iz siječnja. Ako korisnik filtrira travanj, prikazat će se stanje iz ožujka.

Takva logika bolje odgovara stvarnom praćenju streamova jer korisnika ne zanima samo kada je podatak unesen, nego kakvo je bilo zadnje poznato stanje u određenom trenutku.

## Vizualizacija

Stranica za vizualizaciju prikazuje tri grafa:

```text
1. Top 5 pjesama po ukupnom broju streamova
2. Zarada po platformama
3. Stanje streamova kroz vrijeme
```

Prvi graf prikazuje pet pjesama s najvećim ukupnim brojem streamova. Za svaku pjesmu uzima se zadnje poznato stanje streamova po platformama.

Drugi graf prikazuje procijenjenu zaradu po platformama. Zarada se računa prema formuli:

```text
broj_streamova * zarada_po_streamu
```

Treći graf prikazuje promjenu ukupnog stanja streamova kroz vrijeme. Za svaki mjesec aplikacija uzima zadnje poznato stanje streamova za svaku pjesmu i platformu, pa se tako može pratiti rast ukupnih streamova kroz mjesece.

## Napomena o pojednostavljenju

Aplikacija ne računa stvarne tantijeme s obzirom na sve uvjete koji postoje u glazbenoj industriji. Cilj aplikacije je omogućiti jednostavnu evidenciju streamova i procjenu zarade na temelju prosječne zarade po streamu za pojedinu platformu.

Zbog toga je model namjerno pojednostavljen i prilagođen funkcionalnostima koje aplikacija stvarno koristi.
