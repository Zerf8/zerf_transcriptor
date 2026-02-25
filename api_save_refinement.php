<?php
require 'config.php';

header('Content-Type: application/json');

$json = file_get_contents('php://input');
$data = json_decode($json, true);

$youtube_id = $data['youtube_id'] ?? null;
$refined_srt = $data['refined_srt'] ?? null;

if (!$youtube_id || !$refined_srt) {
    echo json_encode(['error' => 'Datos incompletos']);
    exit;
}

try {
    $stmt = $pdo->prepare("
        UPDATE transcriptions t
        JOIN videos v ON t.video_id = v.id
        SET t.refinado_srt = :content
        WHERE v.youtube_id = :yt_id
    ");
    $result = $stmt->execute([
        ':content' => $refined_srt,
        ':yt_id' => $youtube_id
    ]);

    echo json_encode(['success' => $result]);
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
