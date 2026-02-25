<?php
require 'config.php';
try {
    $rows = $pdo->query('SELECT id, video_id, NULLIF(srt_content, "") IS NULL as srt_is_empty, LENGTH(srt_content) as srt_len FROM transcriptions LIMIT 10')->fetchAll();
    print_r($rows);

    $cnt = $pdo->query('SELECT COUNT(*) FROM transcriptions')->fetchColumn();
    echo "Total rows in transcriptions: $cnt\n";

} catch (Exception $e) {
    echo "Error: " . $e->getMessage();
}
