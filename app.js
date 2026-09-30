/* ============================================================
   ADRYNX PHOENIX v8
   APP.JS
   ÉTAPE B — ÉTATS RÉELS DE L'INTERFACE
   ============================================================ */

/*
 * Identifiant de conversation.
 *
 * Il est conservé pendant la session
 * et transmis au backend ADRYNX.
 */

let conversationId = null;


/* ------------------------------------------------------------
   ÉTAT VISUEL DU PHOENIX
   ------------------------------------------------------------ */

function setPhoenixState(state) {

    const body = document.body;

    if (!body) {
        return;
    }

    body.classList.remove(
        "phoenix-idle",
        "phoenix-awake",
        "phoenix-answer",
        "phoenix-error"
    );

    if (
        state === "awake" ||
        state === "answer" ||
        state === "error"
    ) {
        body.classList.add(
            "phoenix-" + state
        );

    } else {

        body.classList.add(
            "phoenix-idle"
        );
    }
}


/* ------------------------------------------------------------
   ÉCHAPPEMENT HTML
   ------------------------------------------------------------ */

function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

}


/* ------------------------------------------------------------
   AFFICHAGE D'UN MESSAGE
   ------------------------------------------------------------ */

function addMessage(role, text, type = "") {

    const chat =
        document.getElementById("chat");

    if (!chat) {
        return;
    }

    const div =
        document.createElement("div");

    div.className =
        "message " +
        role +
        " " +
        type;

    const label =
        role === "user"
            ? "Toi"
            : "ADRYNX";

    div.innerHTML =
        "<b>" +
        label +
        ":</b> " +
        escapeHtml(text);

    chat.appendChild(div);

    chat.scrollTop =
        chat.scrollHeight;

}


/* ------------------------------------------------------------
   ENVOI DEPUIS LE CHAMP
   ------------------------------------------------------------ */

async function send() {

    const input =
        document.getElementById("q");

    if (!input) {
        return;
    }

    const q =
        input.value.trim();

    if (!q) {
        return;
    }

    await ask(q);

}


/* ------------------------------------------------------------
   REQUÊTE PRINCIPALE ADRYNX
   ------------------------------------------------------------ */

async function ask(q) {

    q =
        String(q || "").trim();

    if (!q) {
        return;
    }


    const input =
        document.getElementById("q");

    const status =
        document.getElementById("status");

    const log =
        document.getElementById("log");


    /*
     * Message utilisateur réel.
     */

    addMessage(
        "user",
        q
    );


    /*
     * Nettoyage du champ.
     */

    if (input) {
        input.value = "";
    }


    /*
     * ADRYNX commence réellement
     * la requête backend.
     */

    if (status) {

        status.textContent =
            "État : ADRYNX réfléchit...";

    }

    setPhoenixState("awake");


    try {

        const response =
            await fetch(
                "/api/ask",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        message: q,

                        telephone:
                            "jonathan",

                        conversation_id:
                            conversationId

                    })
                }
            );


        let data = null;


        /*
         * Lecture du JSON réel.
         */

        try {

            data =
                await response.json();

        } catch (jsonError) {

            throw new Error(
                "L'API a envoyé une réponse qui n'est pas du JSON."
            );

        }


        /*
         * Une erreur HTTP réelle
         * ne devient jamais une réponse inventée.
         */

        if (!response.ok) {

            const detail =
                data?.detail ||
                data?.error ||
                "Erreur HTTP " +
                response.status;

            throw new Error(detail);

        }


        /*
         * Le backend doit confirmer
         * que la requête a réussi.
         */

        if (data.ok !== true) {

            throw new Error(
                data.error ||
                data.detail ||
                "ADRYNX a signalé une erreur."
            );

        }


        /*
         * ADRYNX doit fournir
         * une véritable réponse.
         */

        if (
            typeof data.answer !== "string" ||
            !data.answer.trim()
        ) {

            throw new Error(
                "ADRYNX n'a fourni aucune réponse."
            );

        }


        /*
         * Conservation de l'identifiant
         * réel de conversation.
         */

        if (data.conversation_id) {

            conversationId =
                data.conversation_id;

        }


        /*
         * La réponse backend réelle
         * vient d'arriver.
         */

        addMessage(
            "assistant",
            data.answer
        );


        /*
         * État visuel réel :
         * la réponse vient d'être reçue.
         */

        setPhoenixState("answer");


        if (status) {

            status.textContent =
                "État : ADRYNX en ligne";

        }


        if (log) {

            log.textContent =
                "> Réponse reçue\n" +
                "> Source : " +
                (data.source || "backend") +
                "\n" +
                "> Intent : " +
                (data.intent || "non défini") +
                "\n" +
                "> Conversation : " +
                (
                    conversationId ||
                    "non définie"
                );

        }


        /*
         * Retour automatique à l'état
         * normal après l'état de réponse.
         *
         * Le délai sert uniquement à laisser
         * l'interface visuelle exploiter l'état.
         */

        window.setTimeout(
            function() {

                setPhoenixState("idle");

            },
            900
        );


    } catch (error) {

        /*
         * Erreur réelle uniquement.
         * Aucune réponse de remplacement.
         */

        addMessage(
            "assistant",
            "Erreur ADRYNX : " +
            error.message,
            "error"
        );


        setPhoenixState("error");


        if (status) {

            status.textContent =
                "État : ERREUR";

        }


        if (log) {

            log.textContent =
                "> Erreur\n" +
                "> " +
                error.message;

        }


        console.error(
            "ADRYNX ERROR:",
            error
        );


        window.setTimeout(
            function() {

                setPhoenixState("idle");

            },
            1200
        );

    }

}


/* ------------------------------------------------------------
   ENTRÉE CLAVIER
   ------------------------------------------------------------ */

function initializeAdrynxApp() {

    setPhoenixState("idle");


    const input =
        document.getElementById("q");


    if (!input) {
        return;
    }


    input.addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                send();

            }

        }
    );

}


/* ------------------------------------------------------------
   INITIALISATION
   ------------------------------------------------------------ */

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeAdrynxApp
    );

} else {

    initializeAdrynxApp();

}
