/* =====================================================================
   Stölben UI v2 — comportamentos de interface

   Tudo aqui é opcional: nenhuma página depende deste arquivo para
   funcionar ou para ser lida. O que ele faz é o que só o navegador
   pode fazer — contar, preencher, avisar, abrir e mascarar.

   Sem dependências. Carregar no fim do <body> (ou com defer).
   ===================================================================== */
(function () {
    "use strict";

    var semMovimento = window.matchMedia
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function pronto(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else { fn(); }
    }

    /* -----------------------------------------------------------------
       1. NÚMEROS QUE CONTAM
       O indicador conta até o valor mantendo o formato pt-BR que já
       está no HTML. Se o número não for legível, o elemento fica como
       veio — o valor correto nunca depende do JS.
       ----------------------------------------------------------------- */
    function contarNumeros(raiz) {
        if (semMovimento) return;
        (raiz || document).querySelectorAll("[data-ds-conta], .ds-kpi-value").forEach(function (el) {
            if (el.dataset.dsContado === "1") return;
            var partes = /^(\D*?)([\d.,]+)(\D*)$/.exec(el.textContent.trim());
            if (!partes) return;

            var prefixo = partes[1], bruto = partes[2], sufixo = partes[3];
            var casas = /,(\d+)$/.exec(bruto);
            casas = casas ? casas[1].length : 0;
            var alvo = parseFloat(bruto.replace(/\./g, "").replace(",", "."));
            if (!isFinite(alvo) || alvo === 0) return;

            el.dataset.dsContado = "1";
            var fmt = new Intl.NumberFormat("pt-BR", {
                minimumFractionDigits: casas, maximumFractionDigits: casas
            });
            var inicio = null, duracao = 900;
            function passo(agora) {
                if (inicio === null) inicio = agora;
                var t = Math.min((agora - inicio) / duracao, 1);
                var suave = 1 - Math.pow(1 - t, 3);
                el.textContent = prefixo + fmt.format(alvo * suave) + sufixo;
                if (t < 1) window.requestAnimationFrame(passo);
            }
            el.textContent = prefixo + fmt.format(0) + sufixo;
            window.requestAnimationFrame(passo);
        });
    }

    /* -----------------------------------------------------------------
       2. BARRAS QUE PREENCHEM
       A largura final vem de data-ds-progresso="0..100". Sem JS a barra
       fica vazia, então quem precisa do número escreve o número também.
       ----------------------------------------------------------------- */
    function preencherBarras(raiz) {
        (raiz || document).querySelectorAll(".ds-progress-fill").forEach(function (barra) {
            var pct = barra.dataset.dsProgresso;
            if (pct === undefined) return;
            pct = Math.max(0, Math.min(100, parseFloat(pct) || 0));
            if (semMovimento) { barra.style.width = pct + "%"; return; }
            window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () { barra.style.width = pct + "%"; });
            });
        });
    }

    /* -----------------------------------------------------------------
       3. ENVIO EM CURSO
       O botão que enviou o formulário mostra o filete e trava, para o
       clique duplo não virar registro duplicado. Formulários marcados
       com data-ds-sem-busy ficam de fora.
       ----------------------------------------------------------------- */
    function marcarEnvio() {
        document.addEventListener("submit", function (e) {
            var form = e.target;
            if (!form || form.hasAttribute("data-ds-sem-busy")) return;
            var botao = form.querySelector("button[type=submit], .ds-btn[type=submit]");
            if (!botao || botao.classList.contains("is-busy")) return;
            botao.classList.add("is-busy");
            /* Se a navegação não acontecer (validação nativa, erro de
               rede), o botão volta ao normal em vez de ficar travado. */
            window.setTimeout(function () { botao.classList.remove("is-busy"); }, 8000);
        }, true);
    }

    /* -----------------------------------------------------------------
       4. AVISOS
       Some sozinho depois de 6 s; o ponteiro em cima segura o relógio.
       window.dsToast(mensagem, tipo) cria um do zero.
       tipos: success (padrão) | warn | danger | info
       ----------------------------------------------------------------- */
    var ICONES = {
        success: '<path d="M20 6 9 17l-5-5"/>',
        danger:  '<path d="M18 6 6 18M6 6l12 12"/>',
        warn:    '<path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
        info:    '<path d="M12 16v-4m0-4h.01"/><circle cx="12" cy="12" r="10"/>'
    };
    function svg(tipo) {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
            + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + (ICONES[tipo] || ICONES.info) + "</svg>";
    }
    function caixaAvisos() {
        var caixa = document.querySelector("[data-ds-avisos]");
        if (!caixa) {
            caixa = document.createElement("div");
            caixa.className = "ds-avisos";
            caixa.setAttribute("data-ds-avisos", "");
            caixa.setAttribute("role", "status");
            caixa.setAttribute("aria-live", "polite");
            document.body.appendChild(caixa);
        }
        return caixa;
    }
    function fecharAviso(aviso) {
        aviso.classList.add("is-saindo");
        window.setTimeout(function () { aviso.remove(); }, 280);
    }
    function ligarAviso(aviso) {
        if (aviso.dataset.dsLigado === "1") return;
        aviso.dataset.dsLigado = "1";
        var botao = aviso.querySelector(".ds-aviso-fechar");
        if (botao) botao.addEventListener("click", function () { fecharAviso(aviso); });
        var relogio = window.setTimeout(function () { fecharAviso(aviso); }, 6000);
        aviso.addEventListener("mouseenter", function () { window.clearTimeout(relogio); });
        aviso.addEventListener("focusin", function () { window.clearTimeout(relogio); });
    }
    function avisos(raiz) {
        (raiz || document).querySelectorAll(".ds-aviso").forEach(ligarAviso);
    }
    window.dsToast = function (mensagem, tipo) {
        tipo = tipo || "success";
        var aviso = document.createElement("div");
        aviso.className = "ds-aviso ds-aviso--" + tipo;
        aviso.innerHTML =
            '<span class="ds-aviso-marca" aria-hidden="true">' + svg(tipo) + "</span>"
            + "<p></p>"
            + '<button type="button" class="ds-aviso-fechar" aria-label="Dispensar aviso">'
            + svg("danger") + "</button>";
        aviso.querySelector("p").textContent = mensagem;
        caixaAvisos().appendChild(aviso);
        ligarAviso(aviso);
        return aviso;
    };

    /* -----------------------------------------------------------------
       5. MODAIS
       <button data-ds-abre="id-do-dialog"> abre o <dialog class="ds-modal">.
       Clique fora fecha; Esc já é do navegador. O foco volta para o
       gatilho ao fechar — sem isso o teclado se perde na página.
       ----------------------------------------------------------------- */
    function modais(raiz) {
        (raiz || document).querySelectorAll("[data-ds-abre]").forEach(function (botao) {
            if (botao.dataset.dsLigado === "1") return;
            botao.dataset.dsLigado = "1";
            botao.addEventListener("click", function () {
                var dlg = document.getElementById(botao.dataset.dsAbre);
                if (!dlg || typeof dlg.showModal !== "function") return;
                dlg.dataset.dsGatilho = botao.id || "";
                dlg.showModal();
                var primeiro = dlg.querySelector(
                    "input:not([type=hidden]), select, textarea, button:not(.ds-modal-fechar)");
                if (primeiro) primeiro.focus();
            });
        });
        (raiz || document).querySelectorAll("dialog.ds-modal").forEach(function (dlg) {
            if (dlg.dataset.dsLigado === "1") return;
            dlg.dataset.dsLigado = "1";
            dlg.addEventListener("click", function (e) {
                /* Só o clique no próprio <dialog> é clique no fundo: o
                   conteúdo fica dentro de um filho e não dispara aqui. */
                if (e.target === dlg) dlg.close();
            });
            dlg.addEventListener("close", function () {
                var gatilho = dlg.dataset.dsGatilho && document.getElementById(dlg.dataset.dsGatilho);
                if (gatilho) gatilho.focus();
            });
            dlg.querySelectorAll("[data-ds-fecha]").forEach(function (b) {
                b.addEventListener("click", function () { dlg.close(); });
            });
        });
        (raiz || document).querySelectorAll("dialog[data-ds-modal-inicial]").forEach(function (dlg) {
            if (typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
        });
    }

    /* -----------------------------------------------------------------
       6. MOEDA pt-BR
       O campo é escrito como se lê (1.234,56) e volta ao decimal
       canônico no envio, que é o que o servidor aceita.
       Marcar com <input data-ds-moeda>.
       ----------------------------------------------------------------- */
    function centavos(texto) {
        var bruto = String(texto || "").trim();
        if (!bruto) return null;
        /* Valor que já veio do servidor em decimal canônico (1234.56). */
        if (/^-?\d+(\.\d{1,2})$/.test(bruto) && bruto.indexOf(",") < 0) {
            return Math.round(Number(bruto) * 100);
        }
        var negativo = bruto.indexOf("-") >= 0;
        var digitos = bruto.replace(/\D/g, "");
        if (!digitos) return null;
        var valor = parseInt(digitos, 10);
        return negativo ? -valor : valor;
    }
    function moeda(raiz) {
        (raiz || document).querySelectorAll("[data-ds-moeda]").forEach(function (campo) {
            if (campo.dataset.dsLigado === "1") return;
            campo.dataset.dsLigado = "1";
            function formatar() {
                var c = centavos(campo.value);
                campo.value = c === null ? "" : new Intl.NumberFormat("pt-BR", {
                    minimumFractionDigits: 2, maximumFractionDigits: 2
                }).format(c / 100);
            }
            formatar();
            campo.addEventListener("input", function () {
                formatar();
                campo.setSelectionRange(campo.value.length, campo.value.length);
            });
            campo.addEventListener("blur", formatar);
        });
    }
    function normalizarMoedaNoEnvio() {
        document.addEventListener("submit", function (e) {
            e.target.querySelectorAll("[data-ds-moeda]").forEach(function (campo) {
                var c = centavos(campo.value);
                campo.value = c === null ? "" : (c / 100).toFixed(2);
            });
        }, true);
    }

    /* -----------------------------------------------------------------
       7. GAVETA DA LATERAL (mobile)
       O CSS já abre e fecha por :checked — isto só devolve o estado
       para o leitor de tela e fecha a gaveta ao navegar.
       ----------------------------------------------------------------- */
    function gaveta() {
        var toggle = document.querySelector(".ds-nav-toggle");
        var burger = document.querySelector(".ds-burger");
        if (!toggle || !burger) return;
        function sincronizar() {
            burger.setAttribute("aria-expanded", toggle.checked ? "true" : "false");
        }
        toggle.addEventListener("change", sincronizar);
        sincronizar();
        document.querySelectorAll(".ds-nav-link").forEach(function (link) {
            link.addEventListener("click", function () {
                if (toggle.checked) { toggle.checked = false; sincronizar(); }
            });
        });
    }

    /* -----------------------------------------------------------------
       Início. Tudo que aceita raiz é reexecutável: quem troca pedaço de
       página (htmx, fetch + innerHTML) chama window.dsUI.iniciar(no).
       ----------------------------------------------------------------- */
    function iniciarEm(raiz) {
        contarNumeros(raiz);
        preencherBarras(raiz);
        avisos(raiz);
        modais(raiz);
        moeda(raiz);
    }

    window.dsUI = { iniciar: iniciarEm, toast: window.dsToast };

    pronto(function () {
        iniciarEm(document);
        marcarEnvio();
        normalizarMoedaNoEnvio();
        gaveta();
        /* htmx, quando presente, troca pedaços da página. */
        document.body.addEventListener("htmx:afterSwap", function (e) { iniciarEm(e.target); });
    });
})();
