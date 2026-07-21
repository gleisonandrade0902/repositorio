/*
 * PlantGrowth.jsx
 *
 * Script para Adobe After Effects que gera uma planta procedural (arvore
 * ramificada estilo L-system) e anima o crescimento de baixo para cima
 * usando "Trim Paths" em shape layers.
 *
 * Instalacao:
 *   Copie este arquivo para a pasta Scripts do After Effects.
 *   - Windows: C:\Program Files\Adobe\Adobe After Effects <versao>\Support Files\Scripts\
 *   - macOS:   /Applications/Adobe After Effects <versao>/Scripts/
 *   Reinicie o AE e rode em File > Scripts > PlantGrowth.jsx
 *
 * Uso:
 *   1. Abra ou crie uma composicao.
 *   2. Rode o script. Ajuste os parametros na janela.
 *   3. Clique em "Crescer planta".
 *
 * Compativel com AE CC 2018+ (usa apenas API classica de ExtendScript).
 */

(function plantGrowth(thisObj) {

    // -------------------------------------------------------------------
    // Config padrao
    // -------------------------------------------------------------------
    var DEFAULTS = {
        iterations: 6,           // profundidade de recursao dos galhos
        branches: 2,             // galhos por bifurcacao
        angle: 28,               // angulo (graus) entre galhos irmaos
        angleJitter: 8,          // variacao aleatoria do angulo
        initialLength: 140,      // comprimento do tronco (px)
        lengthDecay: 0.72,       // fator de reducao a cada nivel
        strokeStart: 10,         // espessura do tronco
        strokeDecay: 0.68,       // reducao da espessura por nivel
        duration: 4.0,           // duracao total da animacao (s)
        stagger: 0.55,           // sobreposicao entre pai e filho (0-1)
        leafSize: 14,            // tamanho da folha nas pontas
        leafColor: [0.30, 0.75, 0.32],
        branchColor: [0.36, 0.22, 0.10],
        seed: 1
    };

    // -------------------------------------------------------------------
    // PRNG simples e deterministico (Mulberry32)
    // -------------------------------------------------------------------
    function makeRng(seed) {
        var s = (seed >>> 0) || 1;
        return function () {
            s = (s + 0x6D2B79F5) >>> 0;
            var t = s;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    // -------------------------------------------------------------------
    // Geometria: gera a lista de segmentos da planta.
    // Cada segmento = { from:[x,y], to:[x,y], level:int, parentIndex:int }
    // -------------------------------------------------------------------
    function buildPlant(cfg) {
        var rng = makeRng(cfg.seed);
        var segments = [];

        function grow(from, angleDeg, length, level, parentIndex) {
            if (level > cfg.iterations || length < 2) return;

            var rad = angleDeg * Math.PI / 180;
            // No AE, Y cresce para baixo. Queremos crescer para cima,
            // entao subtraimos sin() do Y de origem.
            var to = [
                from[0] + Math.sin(rad) * length,
                from[1] - Math.cos(rad) * length
            ];

            var index = segments.length;
            segments.push({
                from: from,
                to: to,
                level: level,
                parentIndex: parentIndex
            });

            // Ramifica
            var n = cfg.branches;
            var spread = cfg.angle;
            for (var i = 0; i < n; i++) {
                var offset;
                if (n === 1) {
                    offset = 0;
                } else {
                    // distribui entre -spread e +spread
                    offset = -spread + (2 * spread) * (i / (n - 1));
                }
                offset += (rng() - 0.5) * 2 * cfg.angleJitter;
                grow(
                    to,
                    angleDeg + offset,
                    length * cfg.lengthDecay * (0.85 + rng() * 0.3),
                    level + 1,
                    index
                );
            }
        }

        // Ponto inicial: base da composicao
        grow([0, 0], 0, cfg.initialLength, 0, -1);
        return segments;
    }

    // -------------------------------------------------------------------
    // Cria um shape layer com um caminho reto de A ate B e Trim Paths animado
    // -------------------------------------------------------------------
    function createBranchLayer(comp, seg, cfg, startTime, endTime, basePos) {
        var layer = comp.layers.addShape();
        layer.name = "Galho L" + seg.level + "_" + seg.index;
        // O anchor point default do shape layer eh o centro da comp; nos vamos
        // desenhar em coordenadas absolutas dentro do proprio conteudo.

        // Move o shape layer para a base da planta
        layer.property("Transform").property("Position").setValue(basePos);
        layer.property("Transform").property("Anchor Point").setValue([0, 0]);

        var contents = layer.property("ADBE Root Vectors Group");
        var group = contents.addProperty("ADBE Vector Group");
        group.name = "Branch";
        var groupContents = group.property("ADBE Vectors Group");

        // Path
        var pathProp = groupContents.addProperty("ADBE Vector Shape - Group");
        var shape = new Shape();
        shape.vertices = [seg.from, seg.to];
        shape.inTangents = [[0, 0], [0, 0]];
        shape.outTangents = [[0, 0], [0, 0]];
        shape.closed = false;
        pathProp.property("ADBE Vector Shape").setValue(shape);

        // Stroke
        var stroke = groupContents.addProperty("ADBE Vector Graphic - Stroke");
        stroke.property("ADBE Vector Stroke Color").setValue(cfg.branchColor);
        var width = cfg.strokeStart * Math.pow(cfg.strokeDecay, seg.level);
        if (width < 0.6) width = 0.6;
        stroke.property("ADBE Vector Stroke Width").setValue(width);
        stroke.property("ADBE Vector Stroke Line Cap").setValue(2); // round

        // Trim Paths para animar o crescimento
        var trim = groupContents.addProperty("ADBE Vector Filter - Trim");
        var endProp = trim.property("ADBE Vector Trim End");
        endProp.setValueAtTime(startTime, 0);
        endProp.setValueAtTime(endTime, 100);

        // Ease out no keyframe final
        try {
            var easeOut = new KeyframeEase(0, 60);
            endProp.setTemporalEaseAtKey(2, [easeOut], [easeOut]);
        } catch (e) { /* algumas versoes falham silenciosamente */ }

        return layer;
    }

    // -------------------------------------------------------------------
    // Cria uma folha (elipse) na ponta de um galho terminal
    // -------------------------------------------------------------------
    function createLeafLayer(comp, seg, cfg, appearTime, basePos, rng) {
        var layer = comp.layers.addShape();
        layer.name = "Folha L" + seg.level;
        layer.property("Transform").property("Position").setValue(
            [basePos[0] + seg.to[0], basePos[1] + seg.to[1]]
        );

        var contents = layer.property("ADBE Root Vectors Group");
        var group = contents.addProperty("ADBE Vector Group");
        var groupContents = group.property("ADBE Vectors Group");

        var ellipse = groupContents.addProperty("ADBE Vector Shape - Ellipse");
        var size = cfg.leafSize * (0.7 + rng() * 0.6);
        ellipse.property("ADBE Vector Ellipse Size").setValue([size * 0.7, size * 1.4]);

        var fill = groupContents.addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Vector Fill Color").setValue(cfg.leafColor);

        // Rotaciona a folha aleatoriamente
        group.property("ADBE Vector Transform Group")
             .property("ADBE Vector Rotation")
             .setValue((rng() - 0.5) * 180);

        // Anima escala: 0 -> 100 quando o galho termina
        var scale = layer.property("Transform").property("Scale");
        scale.setValueAtTime(appearTime, [0, 0, 100]);
        scale.setValueAtTime(appearTime + 0.35, [110, 110, 100]);
        scale.setValueAtTime(appearTime + 0.55, [100, 100, 100]);

        try {
            var easeOut = new KeyframeEase(0, 75);
            scale.setTemporalEaseAtKey(2, [easeOut, easeOut, easeOut],
                                          [easeOut, easeOut, easeOut]);
        } catch (e) {}

        return layer;
    }

    // -------------------------------------------------------------------
    // Constroi a planta na composicao ativa
    // -------------------------------------------------------------------
    function generate(cfg) {
        var comp = app.project.activeItem;
        if (!(comp && comp instanceof CompItem)) {
            alert("Abra ou selecione uma composicao antes de rodar o script.");
            return;
        }

        app.beginUndoGroup("Growing Plant");

        try {
            var segments = buildPlant(cfg);
            // indexa
            for (var i = 0; i < segments.length; i++) segments[i].index = i;

            // Pasta pai (null) para agrupar tudo
            var parent = comp.layers.addNull();
            parent.name = "Plant Root";
            var basePos = [comp.width / 2, comp.height - 40];
            parent.property("Transform").property("Position").setValue(basePos);

            // Calcula tempos: cada segmento comeca depois que uma fracao do pai cresceu
            var maxLevel = 0;
            for (var j = 0; j < segments.length; j++) {
                if (segments[j].level > maxLevel) maxLevel = segments[j].level;
            }
            var perLevel = cfg.duration / (maxLevel + 1);
            var segDuration = perLevel * (1 + (1 - cfg.stagger));

            var rng = makeRng(cfg.seed + 999);

            for (var k = 0; k < segments.length; k++) {
                var seg = segments[k];
                var start;
                if (seg.parentIndex < 0) {
                    start = 0;
                } else {
                    var parentSeg = segments[seg.parentIndex];
                    start = parentSeg._start + segDuration * cfg.stagger;
                }
                seg._start = start;
                var end = start + segDuration;
                if (end > cfg.duration) end = cfg.duration;

                var layer = createBranchLayer(comp, seg, cfg, start, end, [0, 0]);
                layer.parent = parent;

                // Folha se for terminal (sem filhos)
                var hasChild = false;
                for (var m = k + 1; m < segments.length; m++) {
                    if (segments[m].parentIndex === k) { hasChild = true; break; }
                }
                if (!hasChild) {
                    var leaf = createLeafLayer(comp, seg, cfg, end, [0, 0], rng);
                    leaf.parent = parent;
                }
            }
        } catch (err) {
            alert("Erro ao gerar planta: " + err.toString());
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
            : new Window("palette", "Plant Growth", undefined, { resizeable: true });

        win.orientation = "column";
        win.alignChildren = ["fill", "top"];
        win.spacing = 6;
        win.margins = 12;

        function row(label, initial, min, max) {
            var g = win.add("group");
            g.orientation = "row";
            g.alignChildren = ["left", "center"];
            g.add("statictext", undefined, label).preferredSize.width = 140;
            var input = g.add("edittext", undefined, String(initial));
            input.preferredSize.width = 70;
            input._min = min;
            input._max = max;
            return input;
        }

        var fIter    = row("Iteracoes:",         DEFAULTS.iterations, 1, 9);
        var fBranch  = row("Galhos/bifurcacao:", DEFAULTS.branches, 1, 5);
        var fAngle   = row("Angulo (graus):",    DEFAULTS.angle, 0, 90);
        var fJitter  = row("Variacao angulo:",   DEFAULTS.angleJitter, 0, 45);
        var fLen     = row("Comprimento base:",  DEFAULTS.initialLength, 20, 600);
        var fDecay   = row("Reducao/nivel:",     DEFAULTS.lengthDecay, 0.3, 0.95);
        var fDur     = row("Duracao (s):",       DEFAULTS.duration, 0.5, 30);
        var fStag    = row("Stagger (0-1):",     DEFAULTS.stagger, 0.05, 0.95);
        var fLeaf    = row("Tamanho folha:",     DEFAULTS.leafSize, 2, 60);
        var fSeed    = row("Seed:",              DEFAULTS.seed, 1, 999999);

        var btnGroup = win.add("group");
        btnGroup.alignment = ["fill", "top"];
        btnGroup.alignChildren = ["fill", "center"];

        var btnRand = btnGroup.add("button", undefined, "Nova seed");
        var btnGo   = btnGroup.add("button", undefined, "Crescer planta");

        btnRand.onClick = function () {
            fSeed.text = String(Math.floor(Math.random() * 100000) + 1);
        };

        btnGo.onClick = function () {
            function num(field, fallback) {
                var v = parseFloat(field.text);
                if (isNaN(v)) v = fallback;
                if (field._min !== undefined && v < field._min) v = field._min;
                if (field._max !== undefined && v > field._max) v = field._max;
                return v;
            }
            var cfg = {
                iterations:    Math.round(num(fIter,    DEFAULTS.iterations)),
                branches:      Math.round(num(fBranch,  DEFAULTS.branches)),
                angle:         num(fAngle,   DEFAULTS.angle),
                angleJitter:   num(fJitter,  DEFAULTS.angleJitter),
                initialLength: num(fLen,     DEFAULTS.initialLength),
                lengthDecay:   num(fDecay,   DEFAULTS.lengthDecay),
                strokeStart:   DEFAULTS.strokeStart,
                strokeDecay:   DEFAULTS.strokeDecay,
                duration:      num(fDur,     DEFAULTS.duration),
                stagger:       num(fStag,    DEFAULTS.stagger),
                leafSize:      num(fLeaf,    DEFAULTS.leafSize),
                leafColor:     DEFAULTS.leafColor,
                branchColor:   DEFAULTS.branchColor,
                seed:          Math.round(num(fSeed, DEFAULTS.seed))
            };
            generate(cfg);
        };

        if (win instanceof Window) {
            win.center();
            win.show();
        } else {
            win.layout.layout(true);
        }
    }

    buildUI(thisObj);

})(this);
