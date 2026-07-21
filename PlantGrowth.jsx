/*
 * PlantGrowth.jsx  —  Animador de crescimento de planta para After Effects
 *
 * Voce desenha/importa a arte da planta (caule, raizes, galhos, folhas,
 * frutos) como camadas separadas na sua comp. Este script atribui um
 * "animador" a cada papel e cria as keyframes de crescimento na ordem
 * organica: raizes + caule -> galhos -> folhas -> frutos.
 *
 * Papeis:
 *   Caule    (obrigatorio, 1 camada)   - cresce de baixo pra cima
 *   Raizes   (opcional, N camadas)     - cresce de cima pra baixo
 *   Galhos   (opcional, N camadas)     - crescem escalonados apos o caule
 *   Folhas   (opcional, N camadas)     - "brotam" (scale in) apos galhos
 *   Frutos   (opcional, N camadas)     - "brotam" no final
 *
 * Tecnica de animacao (escolhida automaticamente por camada):
 *   - Shape layer com path -> adiciona Trim Paths e anima End 0->100.
 *     (Desenhe o path com o inicio na base do crescimento.)
 *   - Qualquer outra camada -> anima Scale Y de 0 a 100 com Anchor Point
 *     movido para a base (topo para raizes / centro para folhas/frutos),
 *     compensando Position pra imagem nao pular.
 *
 * Instalacao:
 *   Copie para .../After Effects .../Support Files/Scripts/
 *   ou para Scripts/ScriptUI Panels/ para virar um painel dockavel.
 *   Rode em File > Scripts > PlantGrowth.jsx
 */

(function plantAnimator(thisObj) {

    // -------------------------------------------------------------------
    // Estado da UI: papeis <-> camadas escolhidas
    // -------------------------------------------------------------------
    var STATE = {
        caule:  null,   // Layer
        raizes: [],     // Layer[]
        galhos: [],     // Layer[]
        folhas: [],     // Layer[]
        frutos: []      // Layer[]
    };

    // Config de tempo (segundos e fracoes)
    var CFG = {
        start:         0.0,   // inicio absoluto na timeline
        duration:      4.0,   // duracao total ate a planta estar completa
        stemFraction:  0.55,  // % da duracao total dedicada ao caule
        branchStagger: 0.35,  // apos crescer essa fracao do caule, comecam galhos
        leafGrow:      0.5,   // segundos de brotamento de cada folha
        fruitDelay:    0.75,  // frutos comecam apos essa fracao da duracao
        fruitGrow:     0.6    // segundos de brotamento de cada fruto
    };

    // -------------------------------------------------------------------
    // Utilitarios de camada / geometria
    // -------------------------------------------------------------------

    function getBounds(layer, t) {
        try { return layer.sourceRectAtTime(t, false); } catch (e) { return null; }
    }

    function isShapeLayer(layer) {
        // ShapeLayer nao esta exposto em todas as versoes; testa por matchName.
        try {
            return layer.matchName === "ADBE Vector Layer" ||
                   (layer.property("ADBE Root Vectors Group") != null);
        } catch (e) { return false; }
    }

    function findFirstVectorGroup(shapeLayer) {
        try {
            var root = shapeLayer.property("ADBE Root Vectors Group");
            for (var i = 1; i <= root.numProperties; i++) {
                var p = root.property(i);
                if (p.matchName === "ADBE Vector Group") return p;
            }
        } catch (e) {}
        return null;
    }

    function findExistingTrim(vectorGroup) {
        try {
            var contents = vectorGroup.property("ADBE Vectors Group");
            for (var i = 1; i <= contents.numProperties; i++) {
                if (contents.property(i).matchName === "ADBE Vector Filter - Trim") {
                    return contents.property(i);
                }
            }
        } catch (e) {}
        return null;
    }

    function ensureTrimPaths(shapeLayer) {
        var group = findFirstVectorGroup(shapeLayer);
        if (!group) return null;
        var existing = findExistingTrim(group);
        if (existing) return existing;
        try {
            return group.property("ADBE Vectors Group")
                        .addProperty("ADBE Vector Filter - Trim");
        } catch (e) { return null; }
    }

    // Move o anchor sem que a imagem "pule". Compensa a Position pela
    // diferenca do anchor multiplicada pela Scale atual.
    function setAnchorPreservingPosition(layer, newAnchor) {
        var xform = layer.property("Transform");
        var anchorProp = xform.property("Anchor Point");
        var posProp    = xform.property("Position");
        var scaleProp  = xform.property("Scale");

        var oldA = anchorProp.value;
        var pos  = posProp.value;
        var s    = scaleProp.value;

        var dx = (newAnchor[0] - oldA[0]) * (s[0] / 100);
        var dy = (newAnchor[1] - oldA[1]) * (s[1] / 100);

        // Preserva dimensoes (2D ou 3D)
        var newAnchorFull = (oldA.length === 3) ? [newAnchor[0], newAnchor[1], oldA[2]]
                                                : [newAnchor[0], newAnchor[1]];
        anchorProp.setValue(newAnchorFull);

        if (pos.length === 3) posProp.setValue([pos[0] + dx, pos[1] + dy, pos[2]]);
        else                   posProp.setValue([pos[0] + dx, pos[1] + dy]);
    }

    function bottomCenter(b) { return [b.left + b.width / 2, b.top + b.height]; }
    function topCenter(b)    { return [b.left + b.width / 2, b.top]; }
    function centerOf(b)     { return [b.left + b.width / 2, b.top + b.height / 2]; }

    function easeKey(prop, idx, influence) {
        try {
            var e = new KeyframeEase(0, influence == null ? 75 : influence);
            var n = 1;
            if (prop.value && prop.value.length) n = prop.value.length;
            var arr = [];
            for (var i = 0; i < n; i++) arr.push(e);
            prop.setTemporalEaseAtKey(idx, arr, arr);
        } catch (e) {}
    }

    // -------------------------------------------------------------------
    // Animadores por papel
    // -------------------------------------------------------------------

    // Cresce alongando o layer entre startT e endT.
    // direction: "up" (caule/galhos) ou "down" (raizes).
    function animateGrowth(layer, startT, endT, direction) {
        // Caminho 1: Trim Paths em shape layer.
        if (isShapeLayer(layer)) {
            var trim = ensureTrimPaths(layer);
            if (trim) {
                var endProp = trim.property("ADBE Vector Trim End");
                endProp.setValueAtTime(startT, 0);
                endProp.setValueAtTime(endT, 100);
                easeKey(endProp, 2, 60);
                return true;
            }
        }
        // Caminho 2: Scale Y de 0 a 100 com anchor na base correta.
        var b = getBounds(layer, endT);
        if (!b) {
            // Sem bounds, so anima escala sem mexer no anchor.
            b = { left: 0, top: 0, width: 0, height: 0 };
        } else {
            var anchor = (direction === "down") ? topCenter(b) : bottomCenter(b);
            setAnchorPreservingPosition(layer, anchor);
        }
        var scaleProp = layer.property("Transform").property("Scale");
        var full = scaleProp.value;
        var shrunk;
        if (full.length === 3) shrunk = [full[0], 0, full[2]];
        else                    shrunk = [full[0], 0];

        scaleProp.setValueAtTime(startT, shrunk);
        scaleProp.setValueAtTime(endT,   full);
        easeKey(scaleProp, 2, 60);
        return true;
    }

    // Faz uma camada brotar (scale in com pequeno overshoot).
    function animatePopIn(layer, appearT, growDur) {
        // Ajusta anchor pro centro (evita que a folha "empurre" ao aparecer).
        var b = getBounds(layer, appearT + growDur);
        if (b) setAnchorPreservingPosition(layer, centerOf(b));

        var scaleProp = layer.property("Transform").property("Scale");
        var full = scaleProp.value;
        var zero, over;
        if (full.length === 3) {
            zero = [0, 0, full[2]];
            over = [full[0] * 1.15, full[1] * 1.15, full[2]];
        } else {
            zero = [0, 0];
            over = [full[0] * 1.15, full[1] * 1.15];
        }
        scaleProp.setValueAtTime(appearT, zero);
        scaleProp.setValueAtTime(appearT + growDur * 0.7, over);
        scaleProp.setValueAtTime(appearT + growDur, full);
        easeKey(scaleProp, 3, 75);
    }

    // Remove keyframes de Scale e Trim End das camadas atribuidas
    // (pra permitir "reanimar" sem sujeira).
    function clearAnimationOf(layer) {
        try {
            var scale = layer.property("Transform").property("Scale");
            while (scale.numKeys > 0) scale.removeKey(1);
        } catch (e) {}
        if (isShapeLayer(layer)) {
            var g = findFirstVectorGroup(layer);
            if (g) {
                var trim = findExistingTrim(g);
                if (trim) {
                    try {
                        var endProp   = trim.property("ADBE Vector Trim End");
                        var startProp = trim.property("ADBE Vector Trim Start");
                        while (endProp.numKeys > 0)   endProp.removeKey(1);
                        while (startProp.numKeys > 0) startProp.removeKey(1);
                        endProp.setValue(100);
                        startProp.setValue(0);
                    } catch (e) {}
                }
            }
        }
    }

    // -------------------------------------------------------------------
    // Orquestracao principal
    // -------------------------------------------------------------------

    function collectAllAssigned() {
        var all = [];
        if (STATE.caule) all.push(STATE.caule);
        var groups = [STATE.raizes, STATE.galhos, STATE.folhas, STATE.frutos];
        for (var i = 0; i < groups.length; i++) {
            for (var j = 0; j < groups[i].length; j++) all.push(groups[i][j]);
        }
        return all;
    }

    function runAnimate() {
        if (!STATE.caule) { alert("Atribua uma camada ao Caule."); return; }
        var comp = app.project.activeItem;
        if (!(comp && comp instanceof CompItem)) {
            alert("Ative uma composicao antes de rodar."); return;
        }

        app.beginUndoGroup("Plant Growth: Animate");
        try {
            // Limpa animacoes antigas nas mesmas camadas.
            var all = collectAllAssigned();
            for (var i = 0; i < all.length; i++) clearAnimationOf(all[i]);

            var t0    = CFG.start;
            var total = CFG.duration;
            var stemDur = total * CFG.stemFraction;
            var stemEnd = t0 + stemDur;

            // Raizes: crescem em paralelo ao caule (ate ~110% do tempo do caule).
            for (var r = 0; r < STATE.raizes.length; r++) {
                animateGrowth(STATE.raizes[r], t0, t0 + stemDur * 1.05, "down");
            }

            // Caule
            animateGrowth(STATE.caule, t0, stemEnd, "up");

            // Galhos: cada um comeca quando o caule esta X% crescido, escalonados.
            var branchStart = t0 + stemDur * CFG.branchStagger;
            var branchGrow  = stemDur * 0.7;
            var branchWindow = Math.max(0.001, (stemEnd - branchStart));
            var branchEndTimes = [];
            for (var g = 0; g < STATE.galhos.length; g++) {
                var frac = (STATE.galhos.length > 1) ? (g / (STATE.galhos.length - 1)) : 0;
                var s = branchStart + frac * branchWindow * 0.5;
                var e = s + branchGrow;
                animateGrowth(STATE.galhos[g], s, e, "up");
                branchEndTimes.push(e);
            }

            // Folhas: brotam depois que os galhos (ou o caule) terminam.
            var leafBase = (branchEndTimes.length > 0)
                ? Math.min.apply(null, branchEndTimes)
                : stemEnd;
            var leafSpread = Math.max(0.3, total * 0.25);
            for (var l = 0; l < STATE.folhas.length; l++) {
                var lf = (STATE.folhas.length > 1) ? (l / (STATE.folhas.length - 1)) : 0;
                animatePopIn(STATE.folhas[l], leafBase + lf * leafSpread, CFG.leafGrow);
            }

            // Frutos: aparecem tarde.
            var fruitBase = t0 + total * CFG.fruitDelay;
            var fruitSpread = total * (1 - CFG.fruitDelay) * 0.8;
            for (var f = 0; f < STATE.frutos.length; f++) {
                var ff = (STATE.frutos.length > 1) ? (f / (STATE.frutos.length - 1)) : 0;
                animatePopIn(STATE.frutos[f], fruitBase + ff * fruitSpread, CFG.fruitGrow);
            }

            // Move CTI para o comeco pra facilitar preview.
            comp.time = t0;
        } catch (err) {
            alert("Erro ao animar: " + err.toString());
        } finally {
            app.endUndoGroup();
        }
    }

    function runClear() {
        var all = collectAllAssigned();
        if (all.length === 0) return;
        app.beginUndoGroup("Plant Growth: Clear");
        try {
            for (var i = 0; i < all.length; i++) clearAnimationOf(all[i]);
        } finally {
            app.endUndoGroup();
        }
    }

    // -------------------------------------------------------------------
    // UI
    // -------------------------------------------------------------------

    function buildUI(thisObj) {
        var win = (thisObj instanceof Panel)
            ? thisObj
            : new Window("palette", "Plant Growth Animator", undefined, { resizeable: true });
        win.orientation = "column";
        win.alignChildren = ["fill", "top"];
        win.spacing = 6;
        win.margins = 12;

        function refreshListbox(listbox, roleKey, single) {
            listbox.removeAll();
            var items;
            if (single) items = STATE[roleKey] ? [STATE[roleKey]] : [];
            else        items = STATE[roleKey];
            for (var i = 0; i < items.length; i++) {
                try { listbox.add("item", items[i].name); }
                catch (e) { listbox.add("item", "(camada removida)"); }
            }
        }

        function rolePanel(title, roleKey, single) {
            var p = win.add("panel", undefined, title);
            p.orientation = "column";
            p.alignChildren = ["fill", "top"];
            p.margins = 8;
            p.spacing = 4;

            var lb = p.add("listbox", undefined, []);
            lb.preferredSize = [240, single ? 22 : 60];

            var g = p.add("group");
            g.alignment = ["fill", "top"];
            var bAdd   = g.add("button", undefined, single ? "Definir da selecao"
                                                           : "Adicionar da selecao");
            var bClear = g.add("button", undefined, "Limpar");
            bClear.preferredSize.width = 60;

            refreshListbox(lb, roleKey, single);

            bAdd.onClick = function () {
                var comp = app.project.activeItem;
                if (!(comp && comp instanceof CompItem)) {
                    alert("Ative uma composicao."); return;
                }
                var sel = comp.selectedLayers;
                if (sel.length === 0) {
                    alert("Selecione uma ou mais camadas na comp."); return;
                }
                if (single) {
                    STATE[roleKey] = sel[0];
                } else {
                    for (var i = 0; i < sel.length; i++) {
                        var dup = false;
                        for (var j = 0; j < STATE[roleKey].length; j++) {
                            if (STATE[roleKey][j].index === sel[i].index &&
                                STATE[roleKey][j].containingComp.id === sel[i].containingComp.id) {
                                dup = true; break;
                            }
                        }
                        if (!dup) STATE[roleKey].push(sel[i]);
                    }
                }
                refreshListbox(lb, roleKey, single);
            };

            bClear.onClick = function () {
                STATE[roleKey] = single ? null : [];
                refreshListbox(lb, roleKey, single);
            };
        }

        rolePanel("Caule (obrigatorio)", "caule",  true);
        rolePanel("Raizes",              "raizes", false);
        rolePanel("Galhos",              "galhos", false);
        rolePanel("Folhas",              "folhas", false);
        rolePanel("Frutos",              "frutos", false);

        // Painel de tempo
        var cfgPanel = win.add("panel", undefined, "Tempo");
        cfgPanel.orientation = "column";
        cfgPanel.alignChildren = ["fill", "top"];
        cfgPanel.margins = 8;

        function numRow(parent, label, val) {
            var g = parent.add("group");
            g.add("statictext", undefined, label).preferredSize.width = 130;
            var input = g.add("edittext", undefined, String(val));
            input.preferredSize.width = 70;
            return input;
        }

        var fStart  = numRow(cfgPanel, "Inicio (s):",        CFG.start);
        var fDur    = numRow(cfgPanel, "Duracao total (s):", CFG.duration);
        var fStemF  = numRow(cfgPanel, "Fracao caule:",      CFG.stemFraction);
        var fBS     = numRow(cfgPanel, "Galhos apos (0-1):", CFG.branchStagger);
        var fFD     = numRow(cfgPanel, "Frutos apos (0-1):", CFG.fruitDelay);

        // Acoes
        var actions = win.add("group");
        actions.alignment = ["fill", "top"];
        actions.alignChildren = ["fill", "center"];
        var btnClear = actions.add("button", undefined, "Remover animacao");
        var btnGo    = actions.add("button", undefined, "Animar crescimento");

        btnGo.onClick = function () {
            function num(field, fb) {
                var v = parseFloat(field.text);
                return isNaN(v) ? fb : v;
            }
            CFG.start         = num(fStart,  CFG.start);
            CFG.duration      = num(fDur,    CFG.duration);
            CFG.stemFraction  = num(fStemF,  CFG.stemFraction);
            CFG.branchStagger = num(fBS,     CFG.branchStagger);
            CFG.fruitDelay    = num(fFD,     CFG.fruitDelay);
            runAnimate();
        };

        btnClear.onClick = runClear;

        if (win instanceof Window) { win.center(); win.show(); }
        else                       { win.layout.layout(true); }
    }

    buildUI(thisObj);

})(this);
