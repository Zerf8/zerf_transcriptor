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

    // Get transcriptions: whisper_srt and vtt
    $stmt2 = $pdo->prepare("
        SELECT t.whisper_srt, t.vtt 
        FROM transcriptions t 
        JOIN videos v ON t.video_id = v.id 
        WHERE v.youtube_id = :id
        LIMIT 1
    ");
    $stmt2->execute([':id' => $id]);
    $transcription = $stmt2->fetch();

    $whisperSrt = $transcription ? ($transcription['whisper_srt'] ?? "") : "";
    $youtubeVtt = $transcription ? ($transcription['vtt'] ?? "") : "";

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
        <a href="index.php" class="btn-back">Volver al Dashboard</a>
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

        <!-- COLUMNA 1 DERECHA: VTT -->
        <div class="text-panel">
            <div class="panel-header">
                <span>VTT (YouTube Auto)</span>
                <span class="badge badge-vtt">DB Hostinger</span>
            </div>
            <div class="text-content" id="vtt-content">
                <?= htmlspecialchars($youtubeVtt ?: "No hay VTT guardado en la base de datos.") ?>
            </div>
        </div>

        <!-- COLUMNA 2 DERECHA: SRT -->
        <div class="text-panel">
            <div class="panel-header">
                <span>Whisper SRT</span>
                <span class="badge badge-srt">DB Hostinger</span>
            </div>
            <div class="text-content" id="srt-content">
                <?= htmlspecialchars($whisperSrt ?: "No hay Whisper SRT guardado en la base de datos.") ?>
            </div>
        </div>
    </div>

    <!-- Inject the Subtitles as JS variables safely -->
    <script>
        const youtubeId = "<?= htmlspecialchars($id) ?>";
        const rawSrt = <?= json_encode($whisperSrt) ?>;

        let player;
        let srtData = [];
        let syncInterval;

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

        function timeToSeconds(timeStr) {
            const parts = timeStr.replace(',', '.').split(':');
            if (parts.length === 3) {
                return (parseFloat(parts[0]) * 3600) + (parseFloat(parts[1]) * 60) + parseFloat(parts[2]);
            }
            return 0;
        }

        function parseSRT(text) {
            if (!text) return [];
            const normalized = text.replace(/\r\n/g, '\n');
            const blocks = normalized.trim().split(/\n\s*\n/);
            const parsed = [];
            blocks.forEach(block => {
                const lines = block.split('\n');
                if (lines.length >= 3) {
                    let timeLineIndex = 1;
                    if (!lines[timeLineIndex].includes('-->') && lines.length >= 4) timeLineIndex = 2;

                    const timeLine = lines[timeLineIndex];
                    if (timeLine && timeLine.includes('-->')) {
                        const times = timeLine.split('-->');
                        if (times.length === 2) {
                            const start = timeToSeconds(times[0]);
                            const end = timeToSeconds(times[1]);
                            const subText = lines.slice(timeLineIndex + 1).join('\n');
                            parsed.push({ start, end, text: subText });
                        }
                    }
                }
            });
            return parsed;
        }

        function updateLiveSubtitles() {
            if (!player || !player.getCurrentTime) return;
            const currentTime = player.getCurrentTime();

            let activeText = "";
            for (let i = 0; i < srtData.length; i++) {
                if (currentTime >= srtData[i].start && currentTime <= srtData[i].end) {
                    activeText = srtData[i].text;
                    break;
                }
            }

            document.getElementById('live-text').innerText = activeText || "...";
        }

        // Initialize parser
        srtData = parseSRT(rawSrt);
    </script>
</body>

</html>