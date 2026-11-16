<?php
/**
 * Flovo Content Agency — Poll Endpoint (v1)
 * ====================================
 * الواجهة تستعلم هنا كل 2 ثانية لحد ما تلاقي رد "assistant" جديد بعد
 * رسالة المستخدم. يرجّع كل الرسائل الجديدة (بما فيها ردود الزملاء
 * subbot اللي خلصت لحد دلوقتي) عشان الواجهة تعرض تقدّم الشغل لحظة بلحظة.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: https://conyo.ai');
header('Access-Control-Allow-Credentials: true');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$allowed_host = 'conyo.ai';
$referer = $_SERVER['HTTP_REFERER'] ?? '';
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if (!((stripos($referer, $allowed_host) !== false) || (stripos($origin, $allowed_host) !== false))) {
    http_response_code(403);
    echo json_encode(['error' => 'forbidden']);
    exit;
}

$pdo = new PDO('mysql:host=127.0.0.1;dbname=flovo;charset=utf8mb4', 'flovo', 'hYVnYQgQOQcrZvzJsb8N', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);

$userId = (int)($_GET['user_id'] ?? 0);
$botId = trim($_GET['bot_id'] ?? '');
$sinceId = (int)($_GET['since_id'] ?? 0);

if (!$userId || !$botId) {
    http_response_code(400);
    echo json_encode(['error' => 'bad request']);
    exit;
}

$stmt = $pdo->prepare('SELECT id FROM flovo_agency_conversations WHERE user_id = ? AND bot_id = ?');
$stmt->execute([$userId, $botId]);
$conversationId = $stmt->fetchColumn();

if (!$conversationId) {
    echo json_encode(['ok' => true, 'done' => false, 'messages' => []]);
    exit;
}

$stmt = $pdo->prepare('SELECT id, role, sub_bot_id, content, created_at FROM flovo_agency_messages WHERE conversation_id = ? AND id > ? ORDER BY id ASC');
$stmt->execute([$conversationId, $sinceId]);
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

$done = false;
$messages = [];
foreach ($rows as $r) {
    $messages[] = [
        'id' => (int)$r['id'],
        'role' => $r['role'],
        'sub_bot_id' => $r['sub_bot_id'],
        'content' => $r['content'],
        'created_at' => $r['created_at'],
    ];
    if ($r['role'] === 'assistant') $done = true;
}

echo json_encode(['ok' => true, 'done' => $done, 'conversation_id' => (int)$conversationId, 'messages' => $messages]);
