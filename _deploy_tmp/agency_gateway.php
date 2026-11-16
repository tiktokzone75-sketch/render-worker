<?php
/**
 * Flovo Content Agency — Gateway Endpoint (v1)
 * ====================================
 * نقطة دخول واحدة لفريق الـ6 بوتات + البوت الرئيسي.
 * يعتمد بالكامل على FlovoAIGateway الموجودة فعليًا (نفس بوابة ai_gateway.php) —
 * صفر تعامل مباشر مع أي Provider. الذاكرة مستقلة لكل بوت لكل مستخدم (DB).
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: https://conyo.ai');
header('Access-Control-Allow-Credentials: true');
header('Access-Control-Allow-Methods: POST, OPTIONS');
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

// نعيد استخدام helpers الموجودة في ai_gateway.php (promptBlockChannel, fmtNum...)
// بدون تشغيل أي autorun جوه الملف نفسه.
define('AI_GATEWAY_NO_AUTORUN', true);
require_once '/var/www/html/flovo-api/ai_gateway.php';
require_once '/var/www/html/flovo-api/gateway/gateway.php';
require_once __DIR__ . '/agency_prompts.php';

$pdo = new PDO('mysql:host=127.0.0.1;dbname=flovo;charset=utf8mb4', 'flovo', 'hYVnYQgQOQcrZvzJsb8N', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$gateway = new FlovoAIGateway();

$body = json_decode(file_get_contents('php://input'), true);
$botId = trim($body['bot_id'] ?? '');
$userMessage = trim($body['message'] ?? '');
$userId = (int)($body['user_id'] ?? 0);
$channelData = $body['channel_data'] ?? null;

$catalog = agency_bots_catalog();
if (!$userId || !$botId || !isset($catalog[$botId]) || $userMessage === '') {
    http_response_code(400);
    echo json_encode(['error' => 'bad request']);
    exit;
}

/* ==================== DB helpers ==================== */
function agency_get_conversation(PDO $pdo, int $userId, string $botId): int {
    $stmt = $pdo->prepare('SELECT id FROM flovo_agency_conversations WHERE user_id = ? AND bot_id = ?');
    $stmt->execute([$userId, $botId]);
    $id = $stmt->fetchColumn();
    if ($id) return (int)$id;
    $pdo->prepare('INSERT INTO flovo_agency_conversations (user_id, bot_id) VALUES (?, ?)')->execute([$userId, $botId]);
    return (int)$pdo->lastInsertId();
}

function agency_load_history(PDO $pdo, int $conversationId, int $limit = 24): array {
    $stmt = $pdo->prepare('SELECT role, content FROM flovo_agency_messages WHERE conversation_id = ? AND role IN ("user","assistant") ORDER BY id DESC LIMIT ?');
    $stmt->bindValue(1, $conversationId, PDO::PARAM_INT);
    $stmt->bindValue(2, $limit, PDO::PARAM_INT);
    $stmt->execute();
    $rows = array_reverse($stmt->fetchAll(PDO::FETCH_ASSOC));
    return array_map(fn($r) => ['role' => $r['role'], 'content' => $r['content']], $rows);
}

function agency_save_message(PDO $pdo, int $conversationId, string $role, string $content, ?string $subBotId = null): int {
    $pdo->prepare('INSERT INTO flovo_agency_messages (conversation_id, role, sub_bot_id, content) VALUES (?, ?, ?, ?)')
        ->execute([$conversationId, $role, $subBotId, $content]);
    return (int)$pdo->lastInsertId();
}

/* ==================== Gateway call wrapper ==================== */
function agency_call_once(FlovoAIGateway $gateway, string $systemPrompt, array $history, string $userMessage, float $temperature = 0.7, int $maxTokens = 4000): string {
    $messages = [['role' => 'system', 'content' => $systemPrompt]];
    foreach ($history as $m) { $messages[] = $m; }
    $messages[] = ['role' => 'user', 'content' => $userMessage];

    $response = $gateway->handle('chat', ['messages' => $messages, 'temperature' => $temperature, 'max_tokens' => $maxTokens]);
    if (!$response->success) return '';

    $reply = $response->data['choices'][0]['message']['content'] ?? '';
    $reply = preg_replace('/<think>[\s\S]*?<\/think>/i', '', $reply);
    $reply = preg_replace('/<think>[\s\S]*/i', '', $reply);
    return trim($reply);
}

/* ==================== Scriptwriting pipeline (draft -> review -> fix) ==================== */
function agency_run_scriptwriter(FlovoAIGateway $gateway, array $history, string $userMessage, ?array $channelData, bool $isLoggedIn): array {
    $sysPrompt = agency_build_scriptwriter_prompt($userMessage) . promptBlockChannel($channelData, $isLoggedIn);

    $draft = agency_call_once($gateway, $sysPrompt, $history, $userMessage, 0.7, 6000);
    if (!$draft) return ['reply' => 'حصل تأخير، جرب تاني.', 'draft' => ''];

    $reviewerPrompt = agency_build_reviewer_prompt();
    $reviewInput = "المصدر الأصلي:\n" . $userMessage . "\n\n---\n\nالسكريبت للمراجعة:\n" . $draft;
    $reviewResult = agency_call_once($gateway, $reviewerPrompt, [], $reviewInput, 0.3, 2000);

    if (!$reviewResult || stripos(trim($reviewResult), 'PASS') === 0) {
        return ['reply' => $draft, 'draft' => $draft, 'review' => $reviewResult];
    }

    // فيه ملاحظات مراجعة - اطلب نسخة مُصحَّحة
    $fixPrompt = $sysPrompt . "\n\n[لديك نسخة سابقة من السكريبت ومراجع مستقل رصد المشاكل التالية. أصلحها بدقة في النسخة النهائية فقط بدون شرح خارج السكريبت نفسه.]";
    $fixInput = "السكريبت السابق:\n" . $draft . "\n\nملاحظات المراجع:\n" . $reviewResult . "\n\nالمصدر الأصلي (للرجوع إليه):\n" . $userMessage;
    $fixed = agency_call_once($gateway, $fixPrompt, [], $fixInput, 0.5, 6000);

    return ['reply' => $fixed ?: $draft, 'draft' => $draft, 'review' => $reviewResult];
}

/* ==================== Orchestrator: detect & execute [CALL_BOT:id: task] ==================== */
function agency_run_orchestrator(FlovoAIGateway $gateway, PDO $pdo, array $catalog, array $history, string $userMessage, ?array $channelData, bool $isLoggedIn): array {
    $sysPrompt = $catalog['orchestrator']['system_prompt'] . promptBlockChannel($channelData, $isLoggedIn);
    $firstPass = agency_call_once($gateway, $sysPrompt, $history, $userMessage, 0.6, 2500);

    preg_match_all('/\[CALL_BOT:\s*([a-z_]+)\s*:\s*(.+?)\]/u', $firstPass, $matches, PREG_SET_ORDER);
    if (empty($matches)) {
        return ['reply' => $firstPass, 'subcalls' => []];
    }

    $subResults = [];
    foreach ($matches as $m) {
        $subBotId = trim($m[1]);
        $task = trim($m[2]);
        if (!isset($catalog[$subBotId]) || $subBotId === 'orchestrator') continue;

        if ($subBotId === 'scriptwriting') {
            $r = agency_run_scriptwriter($gateway, [], $task, $channelData, $isLoggedIn);
            $subReply = $r['reply'];
        } else {
            $subSys = $catalog[$subBotId]['system_prompt'] . promptBlockChannel($channelData, $isLoggedIn);
            $subReply = agency_call_once($gateway, $subSys, [], $task, 0.6, 3000);
        }
        $subResults[] = ['bot_id' => $subBotId, 'name' => $catalog[$subBotId]['name'], 'task' => $task, 'reply' => $subReply];
    }

    if (empty($subResults)) {
        return ['reply' => preg_replace('/\[CALL_BOT:.*?\]/u', '', $firstPass), 'subcalls' => []];
    }

    $synthInput = "طلب المستخدم الأصلي:\n" . $userMessage . "\n\n--- نتائج الزملاء ---\n";
    foreach ($subResults as $r) {
        $synthInput .= "\n[{$r['name']}] عن \"{$r['task']}\":\n{$r['reply']}\n";
    }
    $synthSys = $sysPrompt . "\n[دمج النتائج: استلمت ردود الزملاء أدناه. لخّصها في رد واحد مباشر ومفيد للمستخدم، بصيغتك كقائد الفريق، بدون أي علامة [CALL_BOT] في ردك النهائي.]";
    $final = agency_call_once($gateway, $synthSys, [], $synthInput, 0.6, 3500);

    return ['reply' => $final ?: $firstPass, 'subcalls' => $subResults];
}

/* ==================== Main dispatch (async: respond now, work in background) ====================
 * الأورشستريتور وكاتب السكريبت ممكن يستدعوا نموذج AI أكتر من مرة بالتتابع
 * (قد يتجاوز 100-150 ثانية)، وده أطول من حد مهلة بروكسي Cloudflare قدّام
 * الموقع (~100 ثانية). الحل: نرد فورًا بـ "processing" ونكمّل الشغل بعد
 * قطع الاتصال، والواجهة تستعلم (poll) عن طريق agency_poll.php لحد ما
 * تلاقي رسالة assistant جديدة.
 */
$conversationId = agency_get_conversation($pdo, $userId, $botId);
$history = agency_load_history($pdo, $conversationId);
$isLoggedIn = $userId > 0;

$userMsgId = agency_save_message($pdo, $conversationId, 'user', $userMessage);

// رد فوري للمستخدم، وقطع الاتصال، والشغل الحقيقي يكمل بعد كده
// (نفس الطريقة المستخدمة فعليًا وبنجاح في ai_gateway.php)
echo json_encode([
    'ok' => true,
    'status' => 'processing',
    'bot_id' => $botId,
    'conversation_id' => $conversationId,
    'since_id' => $userMsgId,
]);

if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();
}

// ==================== من هنا: الشغل الحقيقي بعد ما العميل خلص استقبال الرد ====================
try {
    if ($botId === 'orchestrator') {
        $result = agency_run_orchestrator($gateway, $pdo, $catalog, $history, $userMessage, $channelData, $isLoggedIn);
        foreach ($result['subcalls'] as $sc) {
            agency_save_message($pdo, $conversationId, 'subbot', $sc['reply'], $sc['bot_id']);
        }
        $reply = $result['reply'];
    } elseif ($botId === 'scriptwriting') {
        $result = agency_run_scriptwriter($gateway, $history, $userMessage, $channelData, $isLoggedIn);
        $reply = $result['reply'];
    } else {
        $sysPrompt = $catalog[$botId]['system_prompt'] . promptBlockChannel($channelData, $isLoggedIn);
        $reply = agency_call_once($gateway, $sysPrompt, $history, $userMessage, 0.7, 4000);
    }
} catch (\Throwable $e) {
    $reply = '';
    error_log('[agency_gateway] exception: ' . $e->getMessage());
}

if (!$reply) {
    $reply = 'حصل تأخير بسيط، ممكن تبعت رسالتك تاني؟';
}

agency_save_message($pdo, $conversationId, 'assistant', $reply);
