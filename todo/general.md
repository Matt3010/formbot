Quando avvio una nuova analisi e immediatamente dopo allo step 2 ritorno indietro e poi ritento una analisi, si crea un'altra
istanza di VNC, quando clicco sui campi, probabilmente vengono selezionati quelli del vnc originale, e non quelli del nuovo vnc.

Prevenire di selezionare con il tool Add field, se presente uno stesso campo in fase VNC.

Auto selezione dello strumento Add field quando si clicca su un campo non già selezionato e auto selezione dello strumento Select mode
quando si clicca su un campo già selezionato, in modo da evitare di dover selezionare manualmente lo strumento ogni volta.

Sistemare la UI per la gestione degli strumenti che appare verticale. Il layout si estende orizzontalmente.

Controllare cosa significa campo "Is required".

Dopo aver cliccato "Confirm Login & Proceed", sistemare l'aggiornamento della UI.
Submitting login form... rimane attivo troppo tempo e non dovrebbe funzionare con un timeout ma con i socket on page load.

Il tasto confirm all dopo aver selezionato i fields su tutti i target deve essere cliccato solo una volta. 
Attualmente il primo click spegne il VNC, il secondo click conferma i fields e procede con l'analisi.

Lo step 3 Workflow Graph ha necessità di un rework grafico in modo tale che sia molto più interattivo e moderno. Un utente consumer
potrebbe non capire cosa fare.

Unire in un unico step 4 e 5, "Options".

Controllare cosa fa Dry Run. Il form non inviato è quello della login? o quello "finale"?

La stealth mode mi serve veramente o dato che uso un client browser vero e proprio i sistemi terzi 
(provider di siti come Apple, Google, etc) non riescono a capire che è un browser reale? 
Se è così, forse è meglio rimuovere questa funzionalità per semplificare l'interfaccia.
Stessa cosa per Action Delay, se non è necessario, meglio rimuoverlo per semplificare l'interfaccia.

Capire cosa è Max Parallel Option e se per una analisi è necessario specificarlo o se di default può essere sempre impostata 
a 1. (Lasciare comunque i controlli sul be se effettivamente è un setting utile per una analisi).

La modifica di un vnc dovrebbe ricompilare i fields che possiede (se ancora validi). Quelli non validi invece dovrebbero essere nella UI 
evidenziati di un colore ad hoc ed eventualmente cancellati.

Permettere all'utente di poter selezionare un file per gli input di tipo file (abbiamo già l'implementazione MINIO).
(Se già non possibile).

Controllare che per tutti i tipi di campi selezionati, la sidebar a destra in fase VNC mostri le opzioni corrette per quel tipo di campo. 
Ad esempio, se è un campo di testo, mostrare le opzioni per il testo, se è un campo di file, mostrare le opzioni per i file, etc.

Sistemare l'url ritornato da MINIO che attualmente punta a http://minio:9000/ invece che al dominio pubblico,
in modo tale che l'utente possa accedere direttamente al file caricato senza dover modificare manualmente l'url.
Lo stesso problema c'è anche per i vari puntamenti del VNC che non so come funzionano.
In generale capire come rendere l'infrastruttura deployabile e accessibile da un dominio pubblico.

Capire quanto è il peso per la macchina di una sessioen VNC.

Il delete di una analisi non aggiorna la UI.

Capire se gli stati di una analisi come "Paused", mi serva davvero. 
Se non è necessario, meglio rimuovere gli stati inutili (mvp) per semplificare l'interfaccia e il flusso di lavoro.
Tra l'altro gli stati non sono allineati.
Vedo usato "paused" ma l'interfaccia non lo permette.
status: 'pending' | 'analyzing' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'editing';

