# Piano cartesiano

Un programmino per aggiungere punti e segmenti a un piano cartesiano.

## Avvio

Serve Python 3.10 o più recente. Dalla cartella del progetto, installa le dipendenze:

```bash
python -m pip install -r requirements.txt
```

Poi avvia il programma:

```bash
python cartesiano.py
```

## Come si usa

- Fai clic sul piano per aggiungere un punto, oppure inserisci le coordinate X e Y nel pannello laterale.
- Tieni premuto **Shift** mentre selezioni due punti, poi premi **Invio** per unirli.
- Seleziona un punto o un segmento e premi **Canc** o **Backspace** per eliminarlo.
- Usa la rotellina per lo zoom e il tasto centrale del mouse per spostarti sul piano.
- Dal menu puoi aprire o salvare un progetto. I progetti vengono salvati in formato JSON.
- Premi **Ctrl+Z** per annullare e **Ctrl+Y** per ripristinare una modifica.

Le coordinate dei punti vengono agganciate alla spaziatura impostata nelle impostazioni della griglia.

## Test

Per eseguire i test, installa anche pytest:

```bash
python -m pip install pytest
python -m pytest
```
