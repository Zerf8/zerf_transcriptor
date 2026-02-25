<?php
require 'config.php';

$id = $_GET['v'] ?? null;
if (!$id) {
    die("Falta parámetro ?v=ID");
}

try {
    // Get video title
    $stmt = $pdo->prepare("SELECT title FROM videos WHERE youtube_id = :id");
    $stmt->execute([':id' => $id]);
    $videoTitle = $stmt->fetchColumn() ?: $id;

    // Get transcriptions: whisper_srt, vtt, refinado_srt, temp_refinado_srt
    $stmt2 = $pdo->prepare("
        SELECT t.whisper_srt, t.vtt, t.refinado_srt, t.temp_refinado_srt
        FROM transcriptions t 
        JOIN videos v ON t.video_id = v.id 
        WHERE v.youtube_id = :id
        LIMIT 1
    ");
    $stmt2->execute([':id' => $id]);
    $transcription = $stmt2->fetch();

    $whisperSrt = $transcription ? ($transcription['whisper_srt'] ?? "") : "";
    $youtubeVtt = $transcription ? ($transcription['vtt'] ?? "") : "";
    
    // Priority Loading Logic: 
    // 1. refinado_srt (Finished)
    // 2. temp_refinado_srt (Draft)
    // 3. None
    $initialRightSrt = "";
    $rightSrtSource = "none";
    if ($transcription && !empty($transcription['refinado_srt'])) {
        $initialRightSrt = $transcription['refinado_srt'];
        $rightSrtSource = "refinado_srt";
    } else if ($transcription && !empty($transcription['temp_refinado_srt'])) {
        $initialRightSrt = $transcription['temp_refinado_srt'];
        $rightSrtSource = "temp_refinado_srt";
    }

} catch (Exception $e) {
    die("Error de base de datos: " . $e->getMessage());
}
?>
<!DOCTYPE html>
<html lang="es">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zerf PHP - Comparador de Subtítulos</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <!-- YouTube Iframe API -->
    <script src="https://www.youtube.com/iframe_api"></script>
    <style>
        :root {
            --primary: #f8c005;
            --secondary: #a70630;
            --bg: #0a0a0c;
            --card-bg: #151518;
            --text: #ffffff;
            --glass: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 1rem 2rem;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            flex-shrink: 0;
        }

        h1 {
            font-size: 2rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: -1px;
            background: linear-gradient(90deg, var(--primary), #fff);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .btn-back {
            background: var(--glass);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 0.7rem 1.5rem;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 700;
            text-transform: uppercase;
            text-decoration: none;
            transition: all 0.2s;
        }

        .btn-back:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--primary);
        }

        .layout {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 1.5rem;
            flex-grow: 1;
            height: 0;
        }

        /* Left Column (Video + Live Subs) */
        .left-col {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .video-wrapper {
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            position: relative;
            padding-top: 56.25%;
        }

        .video-wrapper iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: none;
        }

        .live-subs-box {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            text-align: center;
            position: relative;
            min-height: 150px;
        }

        .live-subs-box::before {
            content: "SUBTÍTULOS EN DIRECTO";
            position: absolute;
            top: 10px;
            left: 15px;
            font-size: 0.7rem;
            color: var(--primary);
            font-weight: 800;
            letter-spacing: 1px;
        }

        .live-text {
            font-size: 1.5rem;
            font-weight: 600;
            line-height: 1.4;
            color: #fff;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
        }

        /* Right Columns (VTT & SRT Texts) */
        .text-panel {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .panel-header {
            padding: 0.8rem 1rem;
            background: rgba(0, 0, 0, 0.5);
            border-bottom: 1px solid var(--border);
            font-weight: 800;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 1px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .badge {
            font-size: 0.65rem;
            padding: 0.2rem 0.6rem;
            border-radius: 100px;
            background: var(--glass);
            border: 1px solid var(--border);
        }

        .badge-srt {
            color: #22c55e;
            border-color: #22c55e;
        }

        .badge-vtt {
            color: #3b82f6;
            border-color: #3b82f6;
        }

        .text-content {
            flex-grow: 1;
            padding: 1rem;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            color: #aaa;
            white-space: pre-wrap;
        }

        ::-webkit-scrollbar {
            width: 6px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--primary);
        }

        .active-sub {
            color: #fff;
            background: rgba(248, 192, 5, 0.15);
            border-left: 2px solid var(--primary);
            padding-left: 5px;
            margin-left: -7px;
            font-weight: 600;
        }
    </style>
</head>

<body>

    <header>
        <div>
            <h1>Previsualizador de Subtítulos</h1>
            <p id="video-title" style="opacity: 0.6; margin-top: 0.2rem; font-size: 1rem;">
                <?= htmlspecialchars($videoTitle) ?>
            </p>
        </div>
        <div style="display: flex; gap: 1rem;">
        <div style="display: flex; gap: 1rem; align-items:center;">
            <span id="save-status" style="font-size: 0.8rem; opacity: 0.7; color: var(--primary);"></span>
            <button id="btn-refine" class="btn-back"
                style="background: var(--secondary); border-color: rgba(255,255,255,0.2);">Refinar con Gemini</button>
            <button id="btn-save" class="btn-back"
                style="background: var(--primary); color: #000; <?php echo ($rightSrtSource === 'none') ? 'opacity: 0.5; cursor: not-allowed;' : ''; ?>" <?php echo ($rightSrtSource === 'none') ? 'disabled' : ''; ?>>Guardar Definitivo</button>
            <a href="index.php" class="btn-back">Volver al Dashboard</a>
        </div>
    </header>

    <div class="layout">
        <!-- MITAD IZQUIERDA: VÍDEO Y SUBS EN DIRECTO -->
        <div class="left-col">
            <div class="video-wrapper">
                <div id="player"></div>
            </div>
            <div class="live-subs-box">
                <div id="live-text" class="live-text">Esperando reproducción...</div>
            </div>
        </div>

        <!-- COLUMNAS DE BLOQUES -->
        <div style="grid-column: span 2; display: flex; flex-direction: column; gap: 1rem; overflow-y: auto; padding-right: 10px;"
            id="blocks-container">
            <!-- Los bloques se generarán aquí con JS -->
        </div>
    </div>

    <style>
        .sub-block {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            display: grid;
            grid-template-columns: 80px 1fr 1fr 1fr;
            gap: 1.5rem;
            transition: all 0.2s;
            position: relative;
        }

        .sub-block.active {
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(248, 192, 5, 0.1);
        }

        .block-time {
            color: var(--primary);
            font-size: 0.8rem;
            font-weight: 800;
        }

        .block-original {
            color: #aaa;
            font-size: 0.95rem;
        }

        .block-suggestion {
            color: #fff;
            font-size: 0.95rem;
            background: rgba(255, 255, 255, 0.03);
            padding: 0.8rem;
            border-radius: 5px;
            border: 1px dashed var(--border);
            display: none;
            width: 100%;
            height: 100%;
            min-height: 80px;
            outline: none;
            resize: vertical;
            overflow: auto;
        }
        .block-suggestion:focus { border-color: var(--primary); }

        .block-suggestion.visible {
            display: block;
        }

        .btn-action {
            color: white;
            border: none;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.7rem;
            cursor: pointer;
            margin-top: 5px;
            display: none;
        }
        .btn-accept { background: #22c55e; }
        .btn-save-edit { background: var(--primary); color: #000; font-weight: bold; }

        .btn-action.visible { display: inline-block; margin-right: 5px; }

        .accepted-indicator {
            color: #22c55e;
            font-size: 0.8rem;
            font-weight: 600;
            display: none;
            margin-top: 8px;
            text-align: right;
            padding-right: 5px;
        }

        .accepted-indicator.visible {
            display: block;
        }
    </style>

    <script>
        const youtubeId = "<?= htmlspecialchars($id) ?>";
        const rawSrt = <?= json_encode($whisperSrt) ?>;
        const rawVtt = <?= json_encode($youtubeVtt) ?>;
        const initialRightSrt = <?= json_encode($initialRightSrt) ?>;
        const rightSrtSource = "<?= $rightSrtSource ?>";

        let player;
        let srtData = [];
        let syncInterval;

        function autoResizeTextarea(textarea) {
            textarea.style.height = 'auto'; // Reset para calcular bien
            let newHeight = textarea.scrollHeight;
            if (newHeight < 80) newHeight = 80; // Mínimo
            textarea.style.height = newHeight + 'px';
        }

        function onYouTubeIframeAPIReady() {
            if (!youtubeId) return;
            player = new YT.Player('player', {
                videoId: youtubeId,
                playerVars: { 'autoplay': 0, 'controls': 1, 'rel': 0 },
                events: { 'onStateChange': onPlayerStateChange }
            });
        }

        function onPlayerStateChange(event) {
            if (event.data == YT.PlayerState.PLAYING) {
                syncInterval = setInterval(updateLiveSubtitles, 100);
            } else {
                clearInterval(syncInterval);
            }
        }

        function updateLiveSubtitles() {
            if (!player || !player.getCurrentTime) return;
            const currentTime = player.getCurrentTime();
            let found = false;

            document.querySelectorAll('.sub-block').forEach((block, index) => {
                const data = srtData[index];
                if (currentTime >= data.start && currentTime <= data.end) {
                    block.classList.add('active');
                    if (!found) {
                        block.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        document.getElementById('live-text').innerText = data.currentText;
                        found = true;
                    }
                } else {
                    block.classList.remove('active');
                }
            });
        }

        function timeToSeconds(timeStr) {
            const parts = timeStr.replace(',', '.').split(':');
            return (parseFloat(parts[0]) * 3600) + (parseFloat(parts[1]) * 60) + parseFloat(parts[2]);
        }

        function parseSRT(text) {
            if (!text) return [];
            // Handle WEBVTT header
            let cleanText = text.replace(/^WEBVTT\s+/i, '');
            // Normalize line breaks
            cleanText = cleanText.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
            const blocks = cleanText.trim().split(/\n\s*\n/);
            return blocks.map((block, i) => {
                const lines = block.split('\n').map(l => l.trim()).filter(l => l !== "");
                if (lines.length < 2) return null;

                let timeLine = "";
                let textLines = [];

                if (lines[0].includes('-->')) {
                    timeLine = lines[0];
                    textLines = lines.slice(1);
                } else if (lines[1] && lines[1].includes('-->')) {
                    timeLine = lines[1];
                    textLines = lines.slice(2);
                } else {
                    return null;
                }

                const times = timeLine.split('-->');
                return {
                    index: i + 1,
                    start: times ? timeToSeconds(times[0].trim()) : 0,
                    end: times ? timeToSeconds(times[1].trim()) : 0,
                    timeStr: timeLine,
                    originalText: textLines.join(' '),
                    currentText: textLines.join(' '),
                    suggestion: null,
                    accepted: false
                };
            }).filter(b => b !== null);
        }

        function renderBlocks() {
            const container = document.getElementById('blocks-container');
            
            const rightTitle = (rightSrtSource === 'refinado_srt') ? 'Definitivo (refinado_srt)' : 'Borrador (temp_refinado_srt)';
            
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: 80px 1fr 1fr 1fr; gap: 1.5rem; padding: 0 1rem 0.5rem 1rem; color: var(--primary); font-weight: bold; font-size: 0.85rem; text-transform: uppercase; border-bottom: 1px solid var(--border); margin-bottom: 0.5rem; flex-shrink: 0;">
                    <div>Tiempo</div>
                    <div>YouTube VTT</div>
                    <div>Whisper SRT</div>
                    <div>${rightTitle}</div>
                </div>
            `;

            const vttBlocks = parseSRT(rawVtt);

            srtData.forEach((block, i) => {
                // Buscar texto VTT superpuesto
                let overlapVtt = "";
                if (vttBlocks.length > 0) {
                    overlapVtt = vttBlocks.filter(v => 
                        (v.start < block.end && v.end > block.start)
                    ).map(v => v.originalText).join(' ');
                }

                const div = document.createElement('div');
                div.className = 'sub-block';
                
                let textToDisplay = block.suggestion ? block.suggestion : "";
                let isDifferent = block.suggestion ? (textToDisplay.trim() !== block.originalText.trim()) : false;

                let suggestionHtml = `
                    <textarea class="block-suggestion visible" id="sug-text-${i}" placeholder="Escribe aquí para editar a mano..." oninput="autoResizeTextarea(this); showSaveBtn(${i})">${textToDisplay}</textarea>
                    <div style="text-align: right;">
                        <button class="btn-action btn-accept ${(!block.accepted && isDifferent) ? 'visible' : ''}" id="btn-acc-${i}" onclick="acceptSuggestion(${i})">Aceptar Cambio</button>
                        <button class="btn-action btn-save-edit" id="btn-save-edit-${i}" onclick="saveManualEdit(${i})">Guardar Bloque</button>
                    </div>
                    <div class="accepted-indicator ${block.accepted ? 'visible' : ''}" id="ind-acc-${i}">✓ SRT Guardado</div>
                `;

                div.innerHTML = `
                    <div class="block-time">${block.timeStr.split('-->')[0].trim()}</div>
                    <div class="block-original" style="opacity: 0.7; font-size: 0.85rem;">${overlapVtt || '-'}</div>
                    <div class="block-original">${block.originalText}</div>
                    <div class="suggestion-area" id="sug-area-${i}" style="display: flex; flex-direction: column;">
                        ${suggestionHtml}
                    </div>
                `;
                container.appendChild(div);
            });
            
            if (rightSrtSource !== 'none') {
                document.getElementById('save-status').innerText = (rightSrtSource === 'refinado_srt') ? "Mostrando Definitivo" : "Mostrando Borrador";
            }
        }

        // Triggers when user types manually in textarea
        function showSaveBtn(index) {
            document.getElementById(`ind-acc-${index}`).classList.remove('visible');
            const acceptBtn = document.getElementById(`btn-acc-${index}`);
            if(acceptBtn) acceptBtn.classList.remove('visible');
            
            document.getElementById(`btn-save-edit-${index}`).classList.add('visible');
            srtData[index].accepted = false;
        }

        // Used when accepting Gemini's original proposal
        function acceptSuggestion(index) {
            const textarea = document.getElementById(`sug-text-${index}`);
            srtData[index].suggestion = textarea.value;
            srtData[index].currentText = textarea.value;
            srtData[index].accepted = true;
            
            document.getElementById(`ind-acc-${index}`).classList.add('visible');
            document.getElementById(`btn-acc-${index}`).classList.remove('visible');
            document.getElementById(`btn-save-edit-${index}`).classList.remove('visible');
            
            saveTempToBg();
        }

        // Used when manually saving an edited block
        function saveManualEdit(index) {
            acceptSuggestion(index);
        }

        async function saveTempToBg() {
            let tempSrt = "";
            srtData.forEach((block, i) => {
                const txtArea = document.getElementById(`sug-text-${i}`);
                let currentVal = block.originalText;
                
                if (txtArea && txtArea.classList.contains('visible') && txtArea.value.trim() !== "") {
                    currentVal = txtArea.value;
                } else if (block.suggestion) {
                    currentVal = block.suggestion;
                }
                
                tempSrt += `${i + 1}\n${block.timeStr}\n${currentVal}\n\n`;
            });

            document.getElementById('save-status').innerText = "Autoguardando...";
            const response = await fetch('api_save_temp.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ youtube_id: youtubeId, temp_srt: tempSrt })
            });
            
            const btnSave = document.getElementById('btn-save');
            btnSave.disabled = false;
            btnSave.style.opacity = '1';
            btnSave.style.cursor = 'pointer';
            
            if (response.ok) {
                document.getElementById('save-status').innerText = "Borrador guardado ✓";
                setTimeout(() => { document.getElementById('save-status').innerText = ""; }, 2000);
            }
        }

        document.getElementById('btn-refine').addEventListener('click', async () => {
            const btn = document.getElementById('btn-refine');
            btn.innerText = "Pensando...";
            btn.disabled = true;

            const response = await fetch(`api_refine.php?v=${youtubeId}`);
            const data = await response.json();

            if (data.refined_raw) {
                // Separar de forma ultra-robusta la respuesta de Gemini tolerando Markdown (** / __), espacios y cualquier salto de línea
                const chunks = data.refined_raw.split(/(?:^|[\r\n]+)\s*(?:\*\*|__)*\[(\d+)\](?:\*\*|__)*\s*/);
                
                // chunks[0] es la basura/texto intro antes del primer corchete
                // chunks[1] es ID 1. chunks[2] es Texto 1. Y así sucesivamente.
                for (let i = 1; i < chunks.length; i += 2) {
                    const idx = parseInt(chunks[i]) - 1;
                    const textContent = (chunks[i + 1] || "").trim();
                    
                    if (srtData[idx]) {
                        srtData[idx].suggestion = textContent;
                        srtData[idx].accepted = false;
                    }
                }
                
                // Refrescar el DOM entero
                renderBlocks();
                // Guardar en BBDD
                saveTempToBg();
            }
            btn.innerText = "Refinar con Gemini";
            btn.disabled = false;
        });

        document.getElementById('btn-save').addEventListener('click', async () => {
            let finalSrt = "";
            srtData.forEach((block, i) => {
                let txt = block.originalText;
                
                // Aplicar el cambio SÓLO si el bloque fue expresamente guardado/aceptado
                if (block.accepted) {
                    const txtArea = document.getElementById(`sug-text-${i}`);
                    if (txtArea && txtArea.classList.contains('visible')) {
                        txt = txtArea.value;
                    } else if (block.suggestion) {
                        txt = block.suggestion;
                    }
                }
                
                finalSrt += `${i + 1}\n${block.timeStr}\n${txt}\n\n`;
            });

            document.getElementById('save-status').innerText = "Guardando definitivo...";
            const response = await fetch('api_save_refinement.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ youtube_id: youtubeId, refined_srt: finalSrt })
            });

            const resData = await response.json();
            if (resData.success) {
                alert("¡Guardado en refinado_srt correctamente!");
                document.getElementById('save-status').innerText = "Mostrando Definitivo";
            } else {
                alert("Error: " + resData.error);
            }
        });

        // Init: Sólo cogemos whisper_srt (rawSrt)
        if (!rawSrt) {
            document.getElementById('blocks-container').innerHTML = '<div style="color:var(--secondary); padding:2rem;">No hay whisper_srt disponible para este vídeo.</div>';
        } else {
            srtData = parseSRT(rawSrt);
            
            // Apply RightSrt payload once
            if (initialRightSrt) {
                let loadedDict = {};
                if (initialRightSrt.trim().startsWith('[')) {
                    try {
                        JSON.parse(initialRightSrt).forEach(b => {
                            loadedDict[b.index] = b.suggestion || b.originalText;
                        });
                    } catch(e) {}
                } else {
                    parseSRT(initialRightSrt).forEach(b => {
                        loadedDict[b.index] = b.currentText;
                    });
                }
                
                srtData.forEach((block) => {
                    let rightText = loadedDict[block.index] || "";
                    // If the text drastically differs from original AND it's not totally empty, mark it
                    if (rightText && rightText.trim() !== block.originalText.trim()) {
                        block.suggestion = rightText;
                        block.currentText = rightText;
                        block.accepted = true; 
                    } else if (rightText === "") { // If rightText is explicitly empty, ensure it's not marked as accepted
                        block.suggestion = "";
                        block.currentText = block.originalText; // Fallback to original text for current display
                        block.accepted = false;
                    }
                });
            }

            renderBlocks();
            
            // Auto-ajustar alturas en cuanto carga
            setTimeout(() => {
                document.querySelectorAll('textarea.block-suggestion').forEach(ta => autoResizeTextarea(ta));
            }, 100);
        }
    </script>
</body>

</html>