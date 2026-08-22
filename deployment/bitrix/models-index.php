<?php
declare(strict_types=1);

define('SITE_ID', 'vc');
define('LANGUAGE_ID', 'en');
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

function h(?string $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function prop(array $properties, string $code): string
{
    $value = $properties[$code]['VALUE'] ?? '';
    if (is_array($value)) {
        $value = reset($value) ?: '';
    }
    return (string) $value;
}

function propList(array $properties, string $code): array
{
    $value = $properties[$code]['VALUE'] ?? [];
    $values = is_array($value) ? $value : [$value];
    return array_values(array_filter(array_map('strval', $values), static fn(string $item): bool => $item !== ''));
}

function loadModels(): array
{
    if (!CModule::IncludeModule('iblock')) {
        throw new RuntimeException('The catalogue storage module is unavailable.');
    }
    $iblock = CIBlock::GetList([], ['TYPE' => 'vercy_registry', '=CODE' => 'vercy_models', 'ACTIVE' => 'Y'])->Fetch();
    if (!$iblock) {
        throw new RuntimeException('The Vercy model catalogue has not been initialized.');
    }

    $base = [];
    $result = CIBlockElement::GetList(
        ['SORT' => 'ASC', 'NAME' => 'ASC'],
        ['IBLOCK_ID' => (int) $iblock['ID'], 'ACTIVE' => 'Y'],
        false,
        false,
        ['ID', 'NAME', 'CODE', 'XML_ID', 'PREVIEW_TEXT']
    );
    while ($row = $result->Fetch()) {
        $base[(int) $row['ID']] = $row;
    }

    $propertyValues = [];
    if ($base !== []) {
        CIBlockElement::GetPropertyValuesArray(
            $propertyValues,
            (int) $iblock['ID'],
            ['ID' => array_keys($base)],
            ['CODE' => [
                'REGISTRY_ID', 'MODEL_ID', 'ENTRY_KIND', 'MODEL_STATUS', 'STATUS_RAW',
                'SPEC_AVAILABLE', 'VERSION', 'FAMILY', 'CATEGORY', 'INDUSTRY',
                'DOMAIN_TAGS', 'TAGS', 'ALTERNATE_NAMES', 'NAV_PATH', 'LEGACY_ALIAS',
                'PAGE_URL', 'SOURCE_URL', 'SPEC_URL', 'AGENTS_URL', 'YAML_URL',
                'PARENT_IDS', 'CONTAINS_IDS', 'ALIGNED_IDS', 'OWNER', 'REVIEW_STATE',
                'ORIGIN', 'NAMESPACE_URI', 'COMPOSITION_ROLE', 'DEFAULT_LINK_TYPE',
                'PRIORITY_WAVE', 'PRIORITY_SCORE', 'PRIORITY_CONFIDENCE',
                'PRIORITY_RATIONALE', 'PROVENANCE',
            ]]
        );
    }

    $models = [];
    foreach ($base as $id => $row) {
        $properties = $propertyValues[$id] ?? [];
        $models[] = [
            'id' => prop($properties, 'MODEL_ID'),
            'registryId' => prop($properties, 'REGISTRY_ID') ?: $row['XML_ID'],
            'name' => $row['NAME'],
            'code' => $row['CODE'],
            'purpose' => $row['PREVIEW_TEXT'],
            'kind' => prop($properties, 'ENTRY_KIND'),
            'status' => prop($properties, 'MODEL_STATUS'),
            'statusRaw' => prop($properties, 'STATUS_RAW'),
            'available' => prop($properties, 'SPEC_AVAILABLE') === 'Y',
            'version' => prop($properties, 'VERSION'),
            'family' => prop($properties, 'FAMILY'),
            'category' => prop($properties, 'CATEGORY'),
            'industry' => propList($properties, 'INDUSTRY'),
            'domain' => propList($properties, 'DOMAIN_TAGS'),
            'tags' => propList($properties, 'TAGS'),
            'alternateNames' => propList($properties, 'ALTERNATE_NAMES'),
            'navPath' => prop($properties, 'NAV_PATH'),
            'legacyAlias' => propList($properties, 'LEGACY_ALIAS'),
            'url' => prop($properties, 'PAGE_URL') ?: '/models/' . rawurlencode($row['CODE']) . '/',
            'sourceUrl' => prop($properties, 'SOURCE_URL'),
            'specUrl' => prop($properties, 'SPEC_URL'),
            'agentsUrl' => prop($properties, 'AGENTS_URL'),
            'yamlUrl' => prop($properties, 'YAML_URL'),
            'parentIds' => propList($properties, 'PARENT_IDS'),
            'containsIds' => propList($properties, 'CONTAINS_IDS'),
            'alignedIds' => propList($properties, 'ALIGNED_IDS'),
            'owner' => prop($properties, 'OWNER'),
            'reviewState' => prop($properties, 'REVIEW_STATE'),
            'origin' => prop($properties, 'ORIGIN'),
            'namespaceUri' => prop($properties, 'NAMESPACE_URI'),
            'compositionRole' => propList($properties, 'COMPOSITION_ROLE'),
            'defaultLinkType' => prop($properties, 'DEFAULT_LINK_TYPE'),
            'priorityWave' => prop($properties, 'PRIORITY_WAVE'),
            'priorityScore' => prop($properties, 'PRIORITY_SCORE'),
            'priorityConfidence' => prop($properties, 'PRIORITY_CONFIDENCE'),
            'priorityRationale' => prop($properties, 'PRIORITY_RATIONALE'),
            'provenance' => prop($properties, 'PROVENANCE'),
        ];
    }
    usort($models, static function (array $left, array $right): int {
        $wave = (int) $left['priorityWave'] <=> (int) $right['priorityWave'];
        if ($wave !== 0) {
            return $wave;
        }
        $score = (float) $right['priorityScore'] <=> (float) $left['priorityScore'];
        return $score !== 0 ? $score : strcasecmp((string) $left['name'], (string) $right['name']);
    });
    return $models;
}

$copy = [
    'en' => [
        'title' => 'Meta-Model Catalogue', 'eyebrow' => 'Specification catalogue',
        'headline' => 'Find the structure your AI needs.',
        'lede' => 'A live registry of versioned meta-model specifications. Search by family, category, industry, domain, name or tags; storage formats and interfaces remain independent.',
        'start' => 'Start new Context World', 'compose' => 'How composing works',
        'notice' => 'AISMM, PLMM and prior World Model assemblies remain available as examples. Planned entries are marked TODO and become buildable when their governed specification is published.',
        'search' => 'Search name, ID or tags…', 'allFamilies' => 'All families',
        'allCategories' => 'All categories', 'allIndustries' => 'All industries',
        'allDomains' => 'All domains', 'allStatuses' => 'All statuses',
        'specifications' => 'meta-models', 'sort' => 'Priority first', 'none' => 'No matching meta-models.',
        'todo' => 'TODO', 'published' => 'Published', 'legacy' => 'Previous version',
        'back' => 'Back to catalogue', 'status' => 'Status', 'kind' => 'Model kind',
        'classifier' => 'Classifier', 'owner' => 'Owner / maintainer', 'priority' => 'Priority',
        'relationships' => 'Composition and relationships', 'parents' => 'Parent models',
        'contains' => 'Contains models', 'aligned' => 'Aligned models',
        'plannedTitle' => 'Specification is planned',
        'plannedText' => 'This catalogue entry defines a governed target, but its Bundle → Layer → Finding → Question / Artifact specification has not been written yet. No placeholder YAML is published as if it were complete.',
        'availableTitle' => 'Specification resources', 'openSpec' => 'Open specification',
        'aiYaml' => 'AI YAML', 'agents' => 'AGENTS.md', 'source' => 'Source repository',
        'world' => 'Create a Context World', 'version' => 'Version', 'wave' => 'wave', 'score' => 'score',
    ],
    'ru' => [
        'title' => 'Каталог мета-моделей', 'eyebrow' => 'Каталог спецификаций',
        'headline' => 'Найдите структуру, которая нужна вашему ИИ.',
        'lede' => 'Живой реестр версионируемых спецификаций мета-моделей. Поиск по семейству, категории, индустрии, области, названию и тегам; форматы хранения и интерфейсы независимы.',
        'start' => 'Создать новый Мир Контекста', 'compose' => 'Как работает композиция',
        'notice' => 'AISMM, PLMM и прежние сборки World Models сохранены как примеры. Планируемые записи отмечены TODO и станут доступны конструктору после публикации управляемой спецификации.',
        'search' => 'Название, ID или теги…', 'allFamilies' => 'Все семейства',
        'allCategories' => 'Все категории', 'allIndustries' => 'Все индустрии',
        'allDomains' => 'Все области', 'allStatuses' => 'Все статусы',
        'specifications' => 'мета-моделей', 'sort' => 'Сначала приоритетные', 'none' => 'Подходящих мета-моделей нет.',
        'todo' => 'TODO', 'published' => 'Опубликована', 'legacy' => 'Предыдущая версия',
        'back' => 'Назад в каталог', 'status' => 'Статус', 'kind' => 'Тип модели',
        'classifier' => 'Классификатор', 'owner' => 'Владелец / сопровождающий', 'priority' => 'Приоритет',
        'relationships' => 'Композиция и связи', 'parents' => 'Родительские модели',
        'contains' => 'Вложенные модели', 'aligned' => 'Связанные модели',
        'plannedTitle' => 'Спецификация запланирована',
        'plannedText' => 'Эта запись задаёт управляемую цель каталога, но структура Бандл → Слой → Сведение → Вопрос / Артефакт ещё не написана. Мы не публикуем фиктивный YAML под видом готовой спецификации.',
        'availableTitle' => 'Ресурсы спецификации', 'openSpec' => 'Открыть спецификацию',
        'aiYaml' => 'YAML для ИИ', 'agents' => 'AGENTS.md', 'source' => 'Исходный репозиторий',
        'world' => 'Создать Мир Контекста', 'version' => 'Версия', 'wave' => 'волна', 'score' => 'оценка',
    ],
    'es' => [
        'title' => 'Catálogo de metamodellos', 'eyebrow' => 'Catálogo de especificaciones',
        'headline' => 'Encuentra la estructura que necesita tu IA.',
        'lede' => 'Registro vivo de especificaciones versionadas. Busca por familia, categoría, industria, dominio, nombre o etiquetas; formatos e interfaces son independientes.',
        'start' => 'Crear un Mundo de Contexto', 'compose' => 'Cómo funciona la composición',
        'notice' => 'AISMM, PLMM y los ensamblajes anteriores se conservan como ejemplos. Las entradas previstas están marcadas TODO.',
        'search' => 'Nombre, ID o etiquetas…', 'allFamilies' => 'Todas las familias', 'allCategories' => 'Todas las categorías',
        'allIndustries' => 'Todas las industrias', 'allDomains' => 'Todos los dominios', 'allStatuses' => 'Todos los estados',
        'specifications' => 'metamodellos', 'sort' => 'Prioridad primero', 'none' => 'No hay coincidencias.', 'todo' => 'TODO',
        'published' => 'Publicado', 'legacy' => 'Versión anterior', 'back' => 'Volver al catálogo', 'status' => 'Estado',
        'kind' => 'Tipo de modelo', 'classifier' => 'Clasificador', 'owner' => 'Propietario', 'priority' => 'Prioridad',
        'relationships' => 'Composición y relaciones', 'parents' => 'Modelos padre', 'contains' => 'Modelos incluidos',
        'aligned' => 'Modelos alineados', 'plannedTitle' => 'Especificación prevista',
        'plannedText' => 'La entrada existe, pero su especificación Bundle → Layer → Finding → Question / Artifact aún no está escrita.',
        'availableTitle' => 'Recursos', 'openSpec' => 'Abrir especificación', 'aiYaml' => 'YAML para IA',
        'agents' => 'AGENTS.md', 'source' => 'Repositorio fuente', 'world' => 'Crear Mundo de Contexto', 'version' => 'Versión', 'wave' => 'ola', 'score' => 'puntuación',
    ],
    'el' => [
        'title' => 'Κατάλογος μετα-μοντέλων', 'eyebrow' => 'Κατάλογος προδιαγραφών', 'headline' => 'Βρείτε τη δομή που χρειάζεται η ΤΝ σας.',
        'lede' => 'Ζωντανό μητρώο εκδόσιμων προδιαγραφών. Αναζήτηση ανά οικογένεια, κατηγορία, κλάδο, τομέα, όνομα ή ετικέτες.',
        'start' => 'Νέος Κόσμος Πλαισίου', 'compose' => 'Πώς λειτουργεί η σύνθεση', 'notice' => 'Τα AISMM, PLMM και οι προηγούμενες συναρμογές παραμένουν ως παραδείγματα. Οι σχεδιαζόμενες εγγραφές φέρουν TODO.',
        'search' => 'Όνομα, ID ή ετικέτες…', 'allFamilies' => 'Όλες οι οικογένειες', 'allCategories' => 'Όλες οι κατηγορίες', 'allIndustries' => 'Όλοι οι κλάδοι', 'allDomains' => 'Όλοι οι τομείς', 'allStatuses' => 'Όλες οι καταστάσεις',
        'specifications' => 'μετα-μοντέλα', 'sort' => 'Προτεραιότητα πρώτα', 'none' => 'Δεν βρέθηκαν αποτελέσματα.', 'todo' => 'TODO', 'published' => 'Δημοσιευμένο', 'legacy' => 'Προηγούμενη έκδοση',
        'back' => 'Πίσω στον κατάλογο', 'status' => 'Κατάσταση', 'kind' => 'Τύπος μοντέλου', 'classifier' => 'Ταξινομητής', 'owner' => 'Ιδιοκτήτης', 'priority' => 'Προτεραιότητα',
        'relationships' => 'Σύνθεση και σχέσεις', 'parents' => 'Γονικά μοντέλα', 'contains' => 'Περιεχόμενα μοντέλα', 'aligned' => 'Ευθυγραμμισμένα μοντέλα',
        'plannedTitle' => 'Η προδιαγραφή έχει προγραμματιστεί', 'plannedText' => 'Η εγγραφή υπάρχει, αλλά η πλήρης προδιαγραφή της δεν έχει ακόμη γραφτεί.',
        'availableTitle' => 'Πόροι προδιαγραφής', 'openSpec' => 'Άνοιγμα προδιαγραφής', 'aiYaml' => 'YAML για ΤΝ', 'agents' => 'AGENTS.md', 'source' => 'Αποθετήριο', 'world' => 'Νέος Κόσμος Πλαισίου', 'version' => 'Έκδοση', 'wave' => 'κύμα', 'score' => 'βαθμός',
    ],
    'zh' => [
        'title' => '元模型目录', 'eyebrow' => '规范目录', 'headline' => '找到您的 AI 所需的数据结构。',
        'lede' => '版本化元模型规范的在线注册表。可按系列、类别、行业、领域、名称或标签搜索；存储格式与接口保持独立。',
        'start' => '创建上下文世界', 'compose' => '了解组合方式', 'notice' => 'AISMM、PLMM 和旧版 World Models 作为示例保留。计划中的条目标记为 TODO。',
        'search' => '搜索名称、ID 或标签…', 'allFamilies' => '全部系列', 'allCategories' => '全部类别', 'allIndustries' => '全部行业', 'allDomains' => '全部领域', 'allStatuses' => '全部状态',
        'specifications' => '个元模型', 'sort' => '按优先级排序', 'none' => '没有匹配的元模型。', 'todo' => 'TODO', 'published' => '已发布', 'legacy' => '旧版本',
        'back' => '返回目录', 'status' => '状态', 'kind' => '模型类型', 'classifier' => '分类器', 'owner' => '所有者 / 维护者', 'priority' => '优先级',
        'relationships' => '组合与关系', 'parents' => '父模型', 'contains' => '包含模型', 'aligned' => '对齐模型',
        'plannedTitle' => '规范已列入计划', 'plannedText' => '此目录条目已经建立，但完整的 Bundle → Layer → Finding → Question / Artifact 规范尚未编写。',
        'availableTitle' => '规范资源', 'openSpec' => '打开规范', 'aiYaml' => 'AI YAML', 'agents' => 'AGENTS.md', 'source' => '源代码仓库', 'world' => '创建上下文世界', 'version' => '版本', 'wave' => '波次', 'score' => '评分',
    ],
];

$language = isset($_GET['lang']) && isset($copy[$_GET['lang']]) ? (string) $_GET['lang'] : 'en';
$t = $copy[$language];

try {
    $models = loadModels();
} catch (Throwable $exception) {
    error_log('Vercy catalogue: ' . $exception->getMessage());
    http_response_code(503);
    header('Content-Type: text/html; charset=UTF-8');
    echo '<!doctype html><html lang="en"><meta charset="utf-8"><title>Catalogue unavailable</title><body><h1>Catalogue temporarily unavailable</h1></body></html>';
    exit;
}

if (($_GET['format'] ?? '') === 'json') {
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: public, max-age=300');
    echo json_encode(['count' => count($models), 'models' => $models], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    exit;
}

$modelCode = isset($_GET['model']) ? trim((string) $_GET['model']) : '';
$currentModel = null;
if ($modelCode !== '') {
    foreach ($models as $candidate) {
        if (hash_equals((string) $candidate['code'], $modelCode)) {
            $currentModel = $candidate;
            break;
        }
    }
    if ($currentModel === null) {
        http_response_code(404);
    }
}

function statusLabel(array $model, array $t): string
{
    return $t[$model['status']] ?? strtoupper((string) $model['status']);
}

function valuesFor(array $models, string $field): array
{
    $values = [];
    foreach ($models as $model) {
        foreach ((array) $model[$field] as $value) {
            if ($value !== '') {
                $values[$value] = true;
            }
        }
    }
    $result = array_keys($values);
    natcasesort($result);
    return array_values($result);
}

header('Content-Type: text/html; charset=UTF-8');
header('Cache-Control: public, max-age=60');
if ($modelCode !== '' && $currentModel === null) {
    CHTTP::SetStatus('404 Not Found');
    header(($_SERVER['SERVER_PROTOCOL'] ?? 'HTTP/1.1') . ' 404 Not Found', true, 404);
}
$canonical = $currentModel ? 'https://ver.cy/models/' . rawurlencode((string) $currentModel['code']) . '/' : 'https://ver.cy/models/';
$pageTitle = $currentModel ? $currentModel['name'] . ' · Vercy' : $t['title'] . ' · Vercy';
$description = $currentModel ? ($currentModel['purpose'] ?: $t['plannedText']) : $t['lede'];
?>
<!doctype html>
<html lang="<?=h($language)?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title><?=h($pageTitle)?></title>
  <meta name="description" content="<?=h($description)?>">
  <link rel="canonical" href="<?=h($canonical)?>">
  <link rel="stylesheet" href="/assets/site.css?v=20260821.11">
  <style>
    .catalog-hero{padding-bottom:36px}.catalog-hero h1{max-width:920px}.catalog-tools{position:sticky;top:68px;z-index:20;background:rgba(8,20,32,.96);border-block:1px solid var(--v-line);padding:18px 0}.catalog-tools-inner{max-width:var(--v-width);margin:auto;padding:0 24px;display:grid;grid-template-columns:2fr repeat(5,1fr);gap:10px}.catalog-tools input,.catalog-tools select{width:100%;min-width:0;border:1px solid var(--v-line);border-radius:9px;background:var(--v-panel);color:var(--v-text);padding:11px 12px}.catalog-body{max-width:var(--v-width);margin:auto;padding:32px 24px 80px}.catalog-meta{display:flex;justify-content:space-between;color:var(--v-muted);margin-bottom:20px}.catalog-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.model-card{display:flex;flex-direction:column;min-height:270px;padding:22px;border:1px solid var(--v-line);border-radius:14px;background:var(--v-panel);text-decoration:none!important;color:var(--v-text)!important;transition:.18s ease}.model-card:hover{border-color:var(--v-cyan);transform:translateY(-2px)}.model-card[hidden]{display:none}.model-top{display:flex;justify-content:space-between;gap:12px;color:var(--v-muted);font-size:12px}.model-card h2{font-size:20px;margin:22px 0 8px}.model-id{font-family:ui-monospace,monospace;color:var(--v-cyan);font-size:12px}.model-purpose{margin:12px 0 0;color:var(--v-muted);font-size:14px;line-height:1.45}.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:18px}.chip,.status-badge{padding:5px 8px;border-radius:99px;background:var(--v-panel-2);color:var(--v-muted);font-size:11px}.status-badge{font-weight:800;letter-spacing:.06em;text-transform:uppercase}.status-todo{background:#392817;color:#ffcb85;border:1px solid #76542a}.status-published{background:#173329;color:#8df1c7;border:1px solid #28624e}.status-legacy{background:#262d37;color:#b8c5d6;border:1px solid #475466}.legacy-note{border:1px solid #5d5130;background:#211e14;color:#d8c991;padding:14px 16px;border-radius:10px;margin-top:22px}.model-detail{max-width:var(--v-width);margin:auto;padding:46px 24px 90px}.detail-back{display:inline-block;margin-bottom:28px}.detail-hero{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:28px;align-items:start}.detail-hero h1{font-size:clamp(38px,6vw,78px);line-height:1;margin:14px 0}.detail-summary{font-size:20px;color:var(--v-muted);max-width:800px}.detail-panel,.detail-section{border:1px solid var(--v-line);border-radius:14px;background:var(--v-panel);padding:22px}.detail-panel dl{margin:20px 0 0}.detail-panel dt{color:var(--v-muted);font-size:12px;margin-top:14px}.detail-panel dd{margin:4px 0 0}.detail-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:28px}.detail-section h2{margin-top:0}.id-list{display:flex;flex-wrap:wrap;gap:8px}.id-list a,.id-list span{font-family:ui-monospace,monospace;font-size:12px;padding:7px 9px;background:var(--v-panel-2);border-radius:7px}.resource-list{display:flex;flex-wrap:wrap;gap:10px}.resource-list a{display:inline-flex;padding:10px 12px;border:1px solid var(--v-line);border-radius:9px;text-decoration:none}.todo-callout{border-color:#76542a;background:#211e14}.todo-callout h2{color:#ffcb85}.muted{color:var(--v-muted)}@media(max-width:1050px){.catalog-tools-inner{grid-template-columns:repeat(3,1fr)}.catalog-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:720px){.catalog-tools{position:static}.catalog-tools-inner,.catalog-grid,.detail-hero,.detail-grid{grid-template-columns:1fr}.catalog-meta{display:block}.catalog-meta span{display:block;margin-bottom:6px}}
  </style>
</head>
<body>
<main>
<?php if ($modelCode !== '' && $currentModel === null): ?>
  <section class="model-detail"><a class="detail-back" href="/models/<?= $language === 'en' ? '' : '?lang=' . h($language) ?>">← <?=h($t['back'])?></a><h1>404</h1><p><?=h($t['none'])?></p></section>
<?php elseif ($currentModel): ?>
  <article class="model-detail">
    <a class="detail-back" href="/models/<?= $language === 'en' ? '' : '?lang=' . h($language) ?>">← <?=h($t['back'])?></a>
    <div class="detail-hero">
      <div>
        <span class="status-badge status-<?=h($currentModel['status'])?>"><?=h(statusLabel($currentModel, $t))?></span>
        <h1><?=h($currentModel['name'])?></h1>
        <div class="model-id"><?=h($currentModel['id'])?> · <?=h($currentModel['registryId'])?></div>
        <p class="detail-summary"><?=h($currentModel['purpose'])?></p>
        <div class="chips">
          <span class="chip"><?=h($currentModel['family'])?></span><span class="chip"><?=h($currentModel['category'])?></span>
          <?php foreach (array_slice($currentModel['domain'], 0, 5) as $domain): ?><span class="chip"><?=h($domain)?></span><?php endforeach; ?>
          <?php foreach (array_slice($currentModel['tags'], 0, 6) as $tag): ?><span class="chip">#<?=h($tag)?></span><?php endforeach; ?>
        </div>
      </div>
      <aside class="detail-panel">
        <span class="model-id"><?=h($currentModel['navPath'])?></span>
        <dl>
          <dt><?=h($t['status'])?></dt><dd><?=h(statusLabel($currentModel, $t))?></dd>
          <dt><?=h($t['kind'])?></dt><dd><?=h($currentModel['kind'])?></dd>
          <dt><?=h($t['version'])?></dt><dd><?=h($currentModel['version'] ?: '—')?></dd>
          <dt><?=h($t['owner'])?></dt><dd><?=h($currentModel['owner'] ?: '—')?></dd>
          <dt><?=h($t['priority'])?></dt><dd><?=h($t['wave'])?> <?=h($currentModel['priorityWave'] ?: '—')?> · <?=h($t['score'])?> <?=h($currentModel['priorityScore'] ?: '—')?></dd>
        </dl>
      </aside>
    </div>
    <div class="detail-grid">
      <?php if ($currentModel['status'] === 'todo'): ?>
        <section class="detail-section todo-callout"><h2><?=h($t['plannedTitle'])?></h2><p><?=h($t['plannedText'])?></p><p class="muted"><?=h($currentModel['priorityRationale'])?></p></section>
      <?php else: ?>
        <section class="detail-section"><h2><?=h($t['availableTitle'])?></h2><div class="resource-list">
          <?php if ($currentModel['url']): ?><a href="<?=h($currentModel['url'])?>"><?=h($t['openSpec'])?></a><?php endif; ?>
          <?php if ($currentModel['yamlUrl']): ?><a href="<?=h($currentModel['yamlUrl'])?>"><?=h($t['aiYaml'])?></a><?php endif; ?>
          <?php if ($currentModel['agentsUrl']): ?><a href="<?=h($currentModel['agentsUrl'])?>"><?=h($t['agents'])?></a><?php endif; ?>
          <?php if ($currentModel['sourceUrl']): ?><a href="<?=h($currentModel['sourceUrl'])?>"><?=h($t['source'])?></a><?php endif; ?>
        </div></section>
      <?php endif; ?>
      <section class="detail-section"><h2><?=h($t['relationships'])?></h2>
        <?php foreach ([['parentIds', 'parents'], ['containsIds', 'contains'], ['alignedIds', 'aligned']] as [$field, $label]): ?>
          <?php if ($currentModel[$field]): ?><p class="muted"><?=h($t[$label])?></p><div class="id-list"><?php foreach ($currentModel[$field] as $id): ?><span><?=h($id)?></span><?php endforeach; ?></div><?php endif; ?>
        <?php endforeach; ?>
        <?php if (!$currentModel['parentIds'] && !$currentModel['containsIds'] && !$currentModel['alignedIds']): ?><p class="muted">—</p><?php endif; ?>
      </section>
      <section class="detail-section"><h2><?=h($t['classifier'])?></h2><p><span class="model-id"><?=h($currentModel['navPath'])?></span></p><p class="muted"><?=h(implode(' · ', $currentModel['compositionRole']))?><?= $currentModel['defaultLinkType'] ? ' · ' . h($currentModel['defaultLinkType']) : '' ?></p></section>
      <section class="detail-section"><h2><?=h($t['world'])?></h2><p class="muted"><?=h($currentModel['provenance'])?></p><div class="resource-list"><a href="/start/?model=<?=rawurlencode($currentModel['id'])?><?= $language === 'en' ? '' : '&amp;lang=' . h($language) ?>"><?=h($t['start'])?></a></div></section>
    </div>
  </article>
<?php else: ?>
  <section class="v-page catalog-hero">
    <span class="v-eyebrow"><?=h($t['eyebrow'])?></span><h1><?=h($t['headline'])?></h1><p class="v-lede"><?=h($t['lede'])?></p>
    <div class="v-actions"><a class="v-button v-button-primary" href="/start/<?= $language === 'en' ? '' : '?lang=' . h($language) ?>"><?=h($t['start'])?></a><a class="v-button" href="/compose/<?= $language === 'en' ? '' : '?lang=' . h($language) ?>"><?=h($t['compose'])?></a></div>
    <div class="legacy-note"><?=h($t['notice'])?></div>
  </section>
  <section class="catalog-tools"><div class="catalog-tools-inner">
    <input id="q" type="search" placeholder="<?=h($t['search'])?>" aria-label="<?=h($t['search'])?>">
    <?php foreach ([
        ['family', 'family', $t['allFamilies']], ['category', 'category', $t['allCategories']],
        ['industry', 'industry', $t['allIndustries']], ['domain', 'domain', $t['allDomains']],
    ] as [$id, $field, $label]): ?>
      <select id="<?=h($id)?>" aria-label="<?=h($label)?>"><option value=""><?=h($label)?></option><?php foreach (valuesFor($models, $field) as $value): ?><option value="<?=h($value)?>"><?=h($value)?></option><?php endforeach; ?></select>
    <?php endforeach; ?>
    <select id="status" aria-label="<?=h($t['allStatuses'])?>"><option value=""><?=h($t['allStatuses'])?></option><?php foreach (['published', 'legacy', 'todo'] as $status): ?><option value="<?=h($status)?>"><?=h($t[$status])?></option><?php endforeach; ?></select>
  </div></section>
  <section class="catalog-body"><div class="catalog-meta"><span><strong id="count"><?=count($models)?></strong> <?=h($t['specifications'])?></span><span><?=h($t['sort'])?></span></div><div class="catalog-grid" id="grid">
    <?php foreach ($models as $model):
        $search = implode(' ', array_merge([$model['name'], $model['id'], $model['registryId'], $model['purpose']], $model['tags'], $model['alternateNames'], $model['legacyAlias']));
    ?>
      <a class="model-card" href="<?=h($model['url'])?><?= $language === 'en' ? '' : (str_contains($model['url'], '?') ? '&amp;' : '?') . 'lang=' . h($language) ?>" data-search="<?=h(mb_strtolower($search))?>" data-family="<?=h($model['family'])?>" data-category="<?=h($model['category'])?>" data-industry="<?=h(implode('||', $model['industry']))?>" data-domain="<?=h(implode('||', $model['domain']))?>" data-status="<?=h($model['status'])?>">
        <div class="model-top"><span><?=h($model['family'])?></span><span class="status-badge status-<?=h($model['status'])?>"><?=h(statusLabel($model, $t))?></span></div>
        <h2><?=h($model['name'])?></h2><div class="model-id"><?=h($model['id'])?></div>
        <?php if ($model['purpose']): ?><p class="model-purpose"><?=h($model['purpose'])?></p><?php endif; ?>
        <div class="chips"><span class="chip"><?=h($model['category'])?></span><?php foreach (array_slice($model['domain'], 0, 2) as $domain): ?><span class="chip"><?=h($domain)?></span><?php endforeach; ?><?php foreach (array_slice($model['tags'], 0, 2) as $tag): ?><span class="chip">#<?=h($tag)?></span><?php endforeach; ?></div>
      </a>
    <?php endforeach; ?>
    <p id="empty" hidden><?=h($t['none'])?></p>
  </div></section>
<?php endif; ?>
</main>
<script src="/assets/site-shell.js?v=20260821.11"></script>
<?php if (!$currentModel && $modelCode === ''): ?>
<script>
(()=>{const cards=[...document.querySelectorAll('.model-card')],q=document.getElementById('q'),filters=['family','category','industry','domain','status'];const render=()=>{const needle=q.value.trim().toLocaleLowerCase(),chosen=Object.fromEntries(filters.map(key=>[key,document.getElementById(key).value]));let count=0;cards.forEach(card=>{const matchesText=!needle||card.dataset.search.includes(needle);const matchesFilters=filters.every(key=>!chosen[key]||(card.dataset[key]||'').split('||').includes(chosen[key]));card.hidden=!(matchesText&&matchesFilters);if(!card.hidden)count++});document.getElementById('count').textContent=String(count);document.getElementById('empty').hidden=count!==0};q.addEventListener('input',render);filters.forEach(key=>document.getElementById(key).addEventListener('change',render))})();
</script>
<?php endif; ?>
<?php if (!isset($_GET['lang'])): ?>
<script>(()=>{const supported=['en','ru','es','el','zh'],stored=localStorage.getItem('vercy-language'),detected=(navigator.language||'en').split('-')[0],language=supported.includes(stored)?stored:(supported.includes(detected)?detected:'en');if(language!=='en'){const url=new URL(location.href);url.searchParams.set('lang',language);location.replace(url.pathname+url.search+url.hash)}})();</script>
<?php endif; ?>
</body></html>
