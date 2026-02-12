# VNC Form Filling UX Rework

Convertire l'attuale gestione di valorizzazione dei form analizzati con VNC e inserimento nei campi veri e propri.

I campi vengono evidenziati tramite HTML e CSS iniettato nella pagina target (overlay, bordi colorati, label).
L'utente può selezionare i campi e correggere gli elementi dal pannello Angular affiancato alla VNC.

---

### 1. Injection Layer (Scraper/Playwright)

Dopo l'analisi AI, iniettare nella pagina target CSS + script minimale che:

- **Evidenzia i campi rilevati**: bordo colorato (blu per input text, verde per select, arancione per checkbox), label floating con nome campo e tipo
- **Numerazione visiva**: badge numerato (1, 2, 3...) corrispondente all'ordine nel FormDefinition
- **Hover effect**: tooltip con selettore CSS attuale e tipo al passaggio del mouse
- **Click-to-select**: click su un campo evidenziato lo seleziona (bordo più spesso, glow) e notifica Python via `page.exposeFunction()`
- **Click su elemento non rilevato**: click su qualsiasi elemento della pagina cattura il selettore CSS e lo propone come nuovo campo

Tecnicamente:
- La comunicazione script↔Python avviene tramite `page.exposeFunction()` (browser→Python) e `page.evaluate()` (Python→browser). Nessun bisogno di postMessage o WebSocket extra
- Il CSS usa `outline` invece di `border` per non alterare il layout della pagina
- Lo script deve essere rimovibile (cleanup) prima dell'esecuzione reale del task
- Per pagine con iframe: iniettare in ogni frame tramite `frame.evaluate()` (Playwright ha accesso a tutti i frame, nessuna restrizione origin)
- Per Shadow DOM: Playwright gestisce nativamente con `>>` piercing selectors
- Re-injection automatica su navigazione/reload tramite `page.on('load')` e `page.on('framenavigated')`

### 2. Pannello Angular (controlli e editing)

Tutti i controlli vivono nel pannello Angular affiancato alla VNC (split view). Nessuna toolbar iniettata nella pagina target (fragile, il CSS del sito la romperebbe).

#### Modalità (toggle nel pannello)
- **Visualizza**: mostra solo gli highlight, nessuna interazione (default)
- **Seleziona**: click su un campo nella VNC lo seleziona per editing nel pannello
- **Aggiungi**: click su qualsiasi elemento nella VNC per aggiungerlo come nuovo campo
- **Rimuovi**: click su un campo evidenziato per rimuoverlo

#### Dettaglio campo selezionato
- **Nome, tipo, selettore CSS** (editabile)
- **Test selettore**: verifica in real-time se il selettore modificato matcha l'elemento giusto (flash verde/rosso nella VNC via `page.evaluate()`)
- **Tipo campo**: dropdown (text, password, email, select, checkbox, radio, file, submit)
- **Valore**: input per inserire/modificare il valore da compilare
- **Sensibile**: toggle per marcare come campo sensibile (encrypted)
- **Conferma campo** / **Scarta campo**
- **Conferma tutti**: salva l'intera configurazione e chiude la sessione VNC
- **Annulla**: chiude senza salvare

#### Lista campi
- Drag&drop per riordinare (Angular CDK `cdkDragDrop`)
- Stato visivo per ogni campo: confermato (verde), da verificare (blu), errore (rosso), aggiunto manualmente (viola)
- Click su un campo nella lista → highlight/scroll nella VNC via `page.evaluate()`

#### Sync bidirezionale
- Click nella VNC → seleziona campo nel pannello (via `page.exposeFunction()` → Pusher → Angular)
- Click nel pannello → highlight/scroll nella VNC (via API scraper → `page.evaluate()`)

### 3. Comunicazione

```
Pagina target (script iniettato)
    ↕ page.exposeFunction() / page.evaluate()
Scraper (FastAPI + Playwright)
    ↕ Pusher broadcast (canale private-analysis.{id})
Frontend (Angular)
    ↕ HTTP API
Backend (Laravel)
```

#### Eventi browser → frontend (via exposeFunction → Pusher)
- `field.selected` — l'utente ha cliccato un campo (selettore, posizione, valore attuale)
- `field.added` — l'utente ha cliccato un elemento non rilevato per aggiungerlo
- `session.confirmed` — l'utente ha confermato tutta la configurazione
- `session.cancelled` — l'utente ha annullato

#### Comandi frontend → browser (via API scraper → page.evaluate)
- `highlight.update` — aggiorna gli highlight dopo modifiche nel pannello
- `field.focus` — evidenzia/scrolla a un campo specifico
- `selector.test` — testa un selettore CSS e mostra il risultato visivamente
- `overlay.cleanup` — rimuovi tutti gli overlay

### 4. Gestione Multi-Step (Login + Target)

Per i flussi login_and_target:

- **Step 1 — Login**: l'utente vede la pagina di login nella VNC, conferma i campi di login, inserisce credenziali
- L'utente può fare login manualmente se necessario (CAPTCHA, 2FA) — come già funziona oggi
- **Step 2 — Target**: dopo il login, la pagina target viene caricata e i campi del form target vengono evidenziati
- Ogni step ha la propria sessione di editing nel pannello
- I form intermedi (pagine di navigazione tra login e target) possono essere aggiunti come step aggiuntivi

### 5. Persistenza e Salvataggio

- Ogni modifica dell'utente viene salvata in tempo reale (debounced) come draft nel record Analysis
- Quando l'utente clicca "Conferma tutti", le FormDefinition e i FormField vengono creati/aggiornati nel backend
- Se l'utente chiude la sessione senza confermare, il draft rimane nell'Analysis e può essere ripreso
- Il campo `Analysis.result` viene arricchito con un campo `user_corrections` che traccia le modifiche manuali

### 6. Casi Limite

- **Selettori ambigui**: se un selettore matcha più elementi, mostrare warning e evidenziare tutti i match
- **Timeout sessione VNC**: se la sessione VNC scade, salvare lo stato e permettere di riprendere

### 7. Ordine di Implementazione Suggerito

1. Script di injection base (highlight campi + numerazione) con `page.evaluate()`
2. Bridge `page.exposeFunction()` per click-to-select
3. Pannello Angular con lista campi e editing
4. Comunicazione scraper↔frontend via Pusher per sync bidirezionale
5. Modalità "Aggiungi campo" e "Rimuovi campo"
6. Test selettore in real-time
7. Gestione multi-step (login + target)
8. Salvataggio draft e persistenza
