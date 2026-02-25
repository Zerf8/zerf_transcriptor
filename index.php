<?php
require 'config.php';

$limit = 25;
$page = isset($_GET['page']) && is_numeric($_GET['page']) ? (int) $_GET['page'] : 1;
if ($page < 1)
    $page = 1;
$offset = ($page - 1) * $limit;

try {
    // Total count of videos with SRT
    $stmtTotal = $pdo->query("SELECT COUNT(*) FROM videos v WHERE EXISTS (SELECT 1 FROM transcriptions t WHERE t.video_id = v.id AND t.whisper_srt IS NOT NULL AND TRIM(t.whisper_srt) != '')");
    $total = $stmtTotal->fetchColumn();
    $totalPages = ceil($total / $limit);

    // Fetch paginated videos
    $stmt = $pdo->prepare("
        SELECT v.id, v.youtube_id, v.title, v.thumbnail, v.upload_date, v.status,
        (SELECT 1 FROM transcriptions t WHERE t.video_id = v.id AND t.whisper_srt IS NOT NULL AND TRIM(t.whisper_srt) != '' LIMIT 1) as has_srt
        FROM videos v
        WHERE EXISTS (SELECT 1 FROM transcriptions t WHERE t.video_id = v.id AND t.whisper_srt IS NOT NULL AND TRIM(t.whisper_srt) != '')
        ORDER BY v.upload_date DESC
        LIMIT :limit OFFSET :offset
    ");
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $videos = $stmt->fetchAll();

    // To prevent total page being 0 if empty
    if ($totalPages == 0)
        $totalPages = 1;

} catch (Exception $e) {
    die("Error Database: " . $e->getMessage());
}
?>
<!DOCTYPE html>
<html lang="es">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zerf PHP Manager - Base de Datos Real</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #f8c005;
            /* Amarillo Zerf */
            --secondary: #a70630;
            /* Granate Zerf */
            --bg: #0a0a0c;
            --card-bg: rgba(255, 255, 255, 0.05);
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
            padding: 2rem;
            background-image:
                radial-gradient(circle at 10% 20%, rgba(167, 6, 48, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(248, 192, 5, 0.1) 0%, transparent 40%);
        }

        header {
            max-width: 1200px;
            margin: 0 auto 3rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: -1px;
            background: linear-gradient(90deg, var(--primary), #fff);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stats {
            display: flex;
            gap: 2rem;
        }

        .stat-item {
            background: var(--glass);
            padding: 0.5rem 1.5rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            text-align: center;
        }

        .stat-val {
            font-weight: 800;
            color: var(--primary);
            font-size: 1.5rem;
        }

        .stat-label {
            font-size: 0.8rem;
            opacity: 0.6;
            text-transform: uppercase;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .video-grid {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .video-card {
            background: var(--card-bg);
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(10px);
            position: relative;
            display: flex;
            flex-direction: row;
            align-items: stretch;
            min-height: 160px;
        }

        .video-card:hover {
            transform: translateY(-4px);
            border-color: var(--primary);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }

        .thumbnail-container {
            width: 280px;
            flex-shrink: 0;
            position: relative;
            background: #000;
        }

        .thumbnail-container img {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .video-info {
            padding: 1.2rem 1.5rem;
            flex-grow: 1;
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
            gap: 2rem;
        }

        .video-info-content {
            flex-grow: 1;
        }

        .video-title {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 0.8rem;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .status-row {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0;
        }

        .badge {
            font-size: 0.75rem;
            padding: 0.3rem 0.8rem;
            border-radius: 100px;
            text-transform: uppercase;
            font-weight: 800;
        }

        .badge-srt {
            background: #22c55e33;
            color: #22c55e;
            border: 1px solid #22c55e;
        }

        .badge-no-srt {
            background: #ef444433;
            color: #ef4444;
            border: 1px solid #ef4444;
        }

        .actions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.6rem;
            min-width: 260px;
            flex-shrink: 0;
        }

        button,
        a.btn {
            padding: 0.7rem;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            font-weight: 700;
            font-size: 0.85rem;
            transition: all 0.2s;
            text-transform: uppercase;
            text-align: center;
            text-decoration: none;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .btn-default {
            background: var(--glass);
            color: var(--text);
            border: 1px solid var(--border);
        }

        .btn-default:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-primary {
            background: var(--primary);
            color: #000;
        }

        .btn-primary:hover {
            transform: scale(1.05);
            background: #fff;
        }

        .pagination {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 3rem;
            margin-bottom: 2rem;
            align-items: center;
            font-weight: 600;
        }

        .pagination a {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            background: var(--glass);
            color: white;
            text-decoration: none;
            border: 1px solid var(--border);
        }

        .pagination a:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .pagination a.disabled {
            opacity: 0.5;
            pointer-events: none;
        }
    </style>
</head>

<body>
    <header>
        <div>
            <h1>PHP Subtitle Manager</h1>
            <p style="opacity: 0.6; margin-top: 5px;">Conectado a MySQL local - Sin cachés - Sin APIs rotas</p>
        </div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-val">
                    <?= number_format($total) ?>
                </div>
                <div class="stat-label">Vídeos SRT OK</div>
            </div>
            <div class="stat-item">
                <div class="stat-val">
                    <?= $page ?> /
                    <?= $totalPages ?>
                </div>
                <div class="stat-label">Página</div>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="video-grid">
            <?php foreach ($videos as $v): ?>
                <?php
                $dateStr = $v['upload_date'] ? date('d/m/Y', strtotime($v['upload_date'])) : 'Pendiente';
                $thumbUrl = $v['thumbnail'] ?: "https://i.ytimg.com/vi/{$v['youtube_id']}/mqdefault.jpg";
                ?>
                <div class="video-card">
                    <div class="thumbnail-container">
                        <a href="https://youtube.com/watch?v=<?= htmlspecialchars($v['youtube_id']) ?>" target="_blank">
                            <img src="<?= htmlspecialchars($thumbUrl) ?>" alt="Miniatura">
                        </a>
                    </div>
                    <div class="video-info">
                        <div class="video-info-content">
                            <a href="https://youtube.com/watch?v=<?= htmlspecialchars($v['youtube_id']) ?>" target="_blank"
                                style="text-decoration:none; color:inherit;">
                                <div class="video-title" title="<?= htmlspecialchars($v['title']) ?>">
                                    <?= htmlspecialchars($v['title']) ?>
                                </div>
                            </a>
                            <div class="status-row">
                                <span class="badge <?= $v['has_srt'] ? 'badge-srt' : 'badge-no-srt' ?>">
                                    <?= $v['has_srt'] ? '✓ SRT LISTO' : '✗ SIN SRT' ?>
                                </span>
                                <span style="font-size: 0.8rem; opacity: 0.5;">
                                    <?= $dateStr ?>
                                </span>
                            </div>
                        </div>
                        <div class="actions">
                            <a href="#" class="btn btn-default"
                                onclick="alert('Funciones en construcción en PHP - Reemplaza los JS si los necesitas o enlaza scripts')">Ver
                                SRT</a>
                            <a href="#" class="btn btn-default">📝 Editar</a>
                            <a href="#" class="btn btn-primary">🚀 Subir SRT</a>
                            <a href="#" class="btn btn-default">Translate EN</a>
                            <a href="compare.php?v=<?= htmlspecialchars($v['youtube_id']) ?>" target="_blank"
                                class="btn btn-default">Revisar</a>
                            <a href="#" class="btn btn-default">🔄 Info</a>
                        </div>
                    </div>
                </div>
            <?php endforeach; ?>

            <?php if (empty($videos)): ?>
                <div style="text-align: center; padding: 4rem; background: var(--glass); border-radius: 16px;">
                    <h2>No se encontraron vídeos con subtítulos finalizados.</h2>
                </div>
            <?php endif; ?>
        </div>

        <div class="pagination">
            <a href="?page=<?= $page - 1 ?>" class="<?= $page <= 1 ? 'disabled' : '' ?>">← Anterior</a>
            <span>Página
                <?= $page ?> de
                <?= $totalPages ?>
            </span>
            <a href="?page=<?= $page + 1 ?>" class="<?= $page >= $totalPages ? 'disabled' : '' ?>">Siguiente →</a>
        </div>
    </div>
</body>

</html>