~~Quando avvio una nuova analisi e immediatamente dopo allo step 2 ritorno indietro e poi ritento una analisi, si crea un'altra
istanza di VNC, quando clicco sui campi, probabilmente vengono selezionati quelli del vnc originale, e non quelli del nuovo vnc.~~

~~Prevenire di selezionare con il tool Add field, se presente uno stesso campo in fase VNC.~~

~~Auto selezione dello strumento Add field quando si clicca su un campo non già selezionato e auto selezione dello strumento Select mode
quando si clicca su un campo già selezionato, in modo da evitare di dover selezionare manualmente lo strumento ogni volta.~~

Sistemare la UI per la gestione degli strumenti che appare verticale. Il layout si estende orizzontalmente.

Controllare cosa significa campo "Is required" di un field.

~~Dopo aver cliccato "Confirm Login & Proceed", sistemare l'aggiornamento della UI.
Submitting login form... rimane attivo troppo tempo e non dovrebbe funzionare con un timeout ma con i socket on page load.~~

Il tasto confirm all dopo aver selezionato i fields su tutti i target deve essere cliccato solo una volta. 
Attualmente il primo click spegne il VNC, il secondo click conferma i fields e procede con l'analisi.

Lo step 3 Workflow Graph ha necessità di un rework grafico in modo tale che sia molto più interattivo e moderno. Un utente consumer
potrebbe non capire cosa fare.

Unire in un unico step 4 e 5, "Options".

Controllare cosa fa Dry Run. Il form non inviato è quello della login? o quello "finale"?

~~La stealth mode mi serve veramente o dato che uso un client browser vero e proprio i sistemi terzi 
(provider di siti come Apple, Google, etc) non riescono a capire che è un browser reale? 
Se è così, forse è meglio rimuovere questa funzionalità per semplificare l'interfaccia.
Stessa cosa per Action Delay, se non è necessario, meglio rimuoverlo per semplificare l'interfaccia.~~

Capire cosa è Max Parallel Option e se per una analisi è necessario specificarlo o se di default può essere sempre impostata 
a 1. (Lasciare comunque i controlli sul be se effettivamente è un setting utile per una analisi).

~~Permettere all'utente di poter selezionare un file per gli input di tipo file (abbiamo già l'implementazione MINIO).
(Se già non possibile).~~

~~Controllare che per tutti i tipi di campi selezionati, la sidebar a destra in fase VNC mostri le opzioni corrette per quel tipo di campo. 
Ad esempio, se è un campo di testo, mostrare le opzioni per il testo, se è un campo di file, mostrare le opzioni per i file, etc.~~

~~Sistemare l'url ritornato da MINIO che attualmente punta a http://minio:9000/ invece che al dominio pubblico,
in modo tale che l'utente possa accedere direttamente al file caricato senza dover modificare manualmente l'url.
Lo stesso problema c'è anche per i vari puntamenti del VNC che non so come funzionano.
In generale capire come rendere l'infrastruttura deployabile e accessibile da un dominio pubblico.~~

Capire quanto è il peso per la macchina di una sessione VNC.

Il delete di una analisi non aggiorna la UI.

~~Capire se gli stati di una analisi come "Paused", mi serva davvero. 
Se non è necessario, meglio rimuovere gli stati inutili (mvp) per semplificare l'interfaccia e il flusso di lavoro.
Tra l'altro gli stati non sono allineati.
Vedo usato "paused" ma l'interfaccia non lo permette.
status: 'pending' | 'analyzing' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'editing';~~

~~tests/test_executor.py::test_execute_simple_single_form FAILED           [ 61%]
tests/test_executor.py::test_execute_multi_step FAILED                   [ 62%]
tests/test_executor.py::test_execute_multi_step_uses_dependency_graph_order FAILED [ 63%]
tests/test_executor.py::test_execute_captcha_triggers_vnc_pause FAILED   [ 65%]
tests/test_executor.py::test_execute_2fa_triggers_post_submit_vnc FAILED [ 66%]
tests/test_executor.py::test_execute_vnc_timeout_fails FAILED            [ 67%]
tests/test_executor.py::test_execute_task_not_found FAILED               [ 68%]
tests/test_executor.py::test_execute_form_selector_not_found FAILED      [ 69%]
tests/test_executor.py::test_execute_stealth_mode FAILED                 [ 70%]
tests/test_executor.py::test_execute_stealth_disabled FAILED             [ 71%]
tests/test_executor.py::test_execute_field_filling_select FAILED         [ 72%]
tests/test_executor.py::test_execute_field_filling_checkbox FAILED       [ 73%]
tests/test_executor.py::test_execute_field_filling_file_upload FAILED    [ 74%]
tests/test_executor.py::test_execute_field_filling_hidden FAILED         [ 75%]
tests/test_executor.py::test_execute_skips_field_with_no_preset FAILED   [ 76%]
tests/test_executor.py::test_execute_field_error_continues FAILED        [ 77%]
tests/test_executor.py::test_execute_dry_run_multi_step FAILED           [ 78%]
tests/test_executor.py::test_no_duplicate_step_in_steps_log_after_captcha FAILED [ 79%]
tests/test_executor.py::test_vnc_cleanup_on_execution_exception FAILED   [ 80%]
tests/test_executor.py::test_vnc_cleanup_on_timeout_failure FAILED
forse è dovuto dall'implementazione di MINIO e gli screenshots?~~

!Ogni sessione dura 30 minuti, inserire un timer di countdown per mostrare all'utente quanto tempo 
rimane prima che la sessione scada, in modo da evitare perdite di dati o interruzioni improvvise durante l'analisi.

!!Dividere lo human breakpoint in Pre submit e Post submit, 
in modo da avere un controllo più granulare sui processi di analisi e permettere
agli utenti di intervenire in momenti specifici del flusso di lavoro.

I test attualmente girano su sqlite, sarebbe bello usare pgsql cosi non è necessario fare una implementazione ad hoc 
per sqlite.

~~!!!!!Differenza tra analysis e tasks? mi serve questa differenza?
Possiamo anche pensare di togliere le analysis da tutta l'infrastruttura e lasciare solo le tasks (se si cancella una task si perde la sessione e si ricomincia da capo), 
in modo da semplificare il modello dati e la gestione delle analisi.
-> (Controlla se questa cosa serve ancora se cancello le analisi e lascio solo le tasks)
La modifica di un vnc dovrebbe ricompilare i fields che possiede (se ancora validi). Quelli non validi invece dovrebbero essere nella UI
evidenziati di un colore ad hoc ed eventualmente cancellati.~~

Quando clicco con un tool su un campo nel VNC, tutto il contenuto si espande e zooma un po. 
Per di piu la view è leggermente tagliata a destra.

Alcuni submit (magari anche altri campi cliccat nel VNC) non hanno un nome. O mettere sempre a tutti qualcosa di default
o risolvere questo bug.

!Gestire elementi che aprono tooltip, modali o elementi in overlay.

Quando scrollo la pagina e ho selezionato precedentemente un tasto submit (forse succede anche con altri campi),
l' highlight del campo è traslato rispetto l' elemento.

!!!!This XML file does not appear to have any style information associated with it. The document tree is shown below.
<Error>
<Code>SignatureDoesNotMatch</Code>
<Message>The request signature we calculated does not match the signature you provided. Check your key and signing method.</Message>
<Key>103/a1166828-0cf6-4617-831c-daddbdbaffbc_final.png</Key>
<BucketName>formbot-screenshots</BucketName>
<Resource>/formbot-screenshots/103/a1166828-0cf6-4617-831c-daddbdbaffbc_final.png</Resource>
<RequestId>18947B4F8A18F205</RequestId>
<HostId>dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8</HostId>
</Error>

Cosa vuol dire filesystem legacy nelle stats su sezione screenshot? Se non serve toglierlo.

Rendere opensource il progetto, in modo da permettere alla community di contribuire allo sviluppo e miglioramento del tool, 
oltre a favorire la trasparenza e la collaborazione tra sviluppatori e utenti interessati al settore della sicurezza informatica.
Scrivere un readme dettagliato che spieghi le funzionalità del tool, come installarlo e utilizzarlo, e come contribuire al progetto, in modo da facilitare l'adozione e la partecipazione della community.
Includere la licenza open source appropriata per il progetto, in modo da garantire che il codice sia utilizzabile e modificabile da chiunque, nel rispetto dei diritti degli autori originali.