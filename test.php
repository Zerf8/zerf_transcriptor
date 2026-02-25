<?php
require 'config.php';
try {
    $count = $pdo->query('SELECT COUNT(*) FROM videos')->fetchColumn();
    echo "Videos count: $count\n";

    $countSrt = $pdo->query("SELECT COUNT(*) FROM videos v WHERE EXISTS (SELECT 1 FROM transcriptions t WHERE t.video_id = v.id AND t.srt_content IS NOT NULL AND TRIM(t.srt_content) != '')")->fetchColumn();
    echo "Videos with SRT count query 1: $countSrt\n";

    $countAnySrt = $pdo->query("SELECT COUNT(*) FROM transcriptions WHERE srt_content IS NOT NULL AND TRIM(srt_content) != ''")->fetchColumn();
    echo "Total SRTs: $countAnySrt\n";

} catch (Exception $e) {
    echo "Error: " . $e->getMessage();
}
