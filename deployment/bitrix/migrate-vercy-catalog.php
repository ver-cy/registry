<?php
declare(strict_types=1);

/**
 * Idempotently create and populate the Vercy Bitrix catalogue information blocks.
 *
 * Run on the host:
 *   php /data/web/www/ver.cy/tools/server/migrate-vercy-catalog.php
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

set_time_limit(0);
ini_set('memory_limit', '1024M');

$documentRoot = dirname(__DIR__, 2);
$importPath = __DIR__ . '/vercy-catalog-import.json';
if (!is_file($importPath)) {
    fwrite(STDERR, "Import payload not found: {$importPath}\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'ver.cy';
$_SERVER['SERVER_NAME'] = 'ver.cy';
$_SERVER['REQUEST_URI'] = '/tools/server/migrate-vercy-catalog.php';

define('SITE_ID', 'vc');
define('LANGUAGE_ID', 'en');
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
define('BX_CRONTAB', true);

require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

if (!CModule::IncludeModule('iblock')) {
    fwrite(STDERR, "Bitrix iblock module is unavailable\n");
    exit(3);
}

$payload = json_decode((string) file_get_contents($importPath), true, 512, JSON_THROW_ON_ERROR);
if (($payload['counts']['models'] ?? 0) !== 403 || ($payload['counts']['interoperability'] ?? 0) !== 1180) {
    fwrite(STDERR, "Refusing an incomplete import payload\n");
    exit(4);
}

const IBLOCK_TYPE = 'vercy_registry';
const MODEL_IBLOCK_CODE = 'vercy_models';
const INTEROP_IBLOCK_CODE = 'vercy_interoperability';

$propertyDefinitions = [
    'REGISTRY_ID' => ['Registry ID', 'S', false, true],
    'MODEL_ID' => ['Model ID', 'S', false, true],
    'RECORD_PLANE' => ['Record plane', 'S', false, true],
    'ENTRY_KIND' => ['Entry kind', 'S', false, true],
    'MODEL_STATUS' => ['Catalogue status', 'S', false, true],
    'STATUS_RAW' => ['Source status', 'S', false, true],
    'SPEC_AVAILABLE' => ['Specification available', 'S', false, true],
    'VERSION' => ['Specification version', 'S', false, true],
    'FAMILY' => ['Family', 'S', false, true],
    'CATEGORY' => ['Category', 'S', false, true],
    'INDUSTRY' => ['Industries', 'S', true, true],
    'DOMAIN_TAGS' => ['Domains', 'S', true, true],
    'TAGS' => ['Tags', 'S', true, true],
    'ALTERNATE_NAMES' => ['Alternate names', 'S', true, true],
    'NAV_PATH' => ['Navigation classifier path', 'S', false, true],
    'LEGACY_ALIAS' => ['Legacy aliases', 'S', true, true],
    'PAGE_URL' => ['Public page URL', 'S', false, false],
    'SOURCE_URL' => ['Primary source URL', 'S', false, false],
    'SPEC_URL' => ['Specification URL', 'S', false, false],
    'AGENTS_URL' => ['AGENTS.md URL', 'S', false, false],
    'YAML_URL' => ['AI YAML URL', 'S', false, false],
    'EXISTING_SPEC_REF' => ['Previous specification references', 'S', true, false],
    'PARENT_IDS' => ['Parent model IDs', 'S', true, true],
    'CONTAINS_IDS' => ['Contained model IDs', 'S', true, true],
    'ALIGNED_IDS' => ['Aligned model IDs', 'S', true, true],
    'OWNER' => ['Owner or maintainer', 'S', false, true],
    'REVIEW_STATE' => ['Review state', 'S', false, true],
    'ORIGIN' => ['Registry origin', 'S', false, true],
    'NAMESPACE_URI' => ['Namespace URI', 'S', false, false],
    'SOURCE_VERSION' => ['Source version or year', 'S', false, true],
    'SOURCE_GROUP' => ['Source group', 'S', false, true],
    'SOURCE_CATEGORY' => ['Source category', 'S', false, true],
    'SOURCE_FORMAT' => ['Source format', 'S', false, true],
    'COMPOSITION_ROLE' => ['Composition roles', 'S', true, true],
    'DEFAULT_LINK_TYPE' => ['Default link type', 'S', false, true],
    'PRIORITY_WAVE' => ['Priority wave', 'N', false, true],
    'PRIORITY_SCORE' => ['Priority score', 'N', false, true],
    'PRIORITY_CONFIDENCE' => ['Priority confidence', 'S', false, true],
    'PRIORITY_RATIONALE' => ['Priority rationale', 'S', false, false],
    'RELATIONS_REF' => ['Relations registry reference', 'S', false, false],
    'PROVENANCE' => ['Provenance', 'S', false, false],
    'IMPORT_BATCH' => ['Last import timestamp', 'S', false, true],
];

function bitrixError(string $fallback, object $entity): RuntimeException
{
    $message = property_exists($entity, 'LAST_ERROR') ? trim((string) $entity->LAST_ERROR) : '';
    return new RuntimeException($message !== '' ? $message : $fallback);
}

function ensureIblockType(): void
{
    global $DB, $CACHE_MANAGER;
    $existing = $DB->Query("SELECT ID FROM b_iblock_type WHERE ID='" . $DB->ForSql(IBLOCK_TYPE) . "'")->Fetch();
    if ($existing) {
        $CACHE_MANAGER->CleanDir('b_iblock_type');
        return;
    }

    $languages = [];
    $result = CLanguage::GetList($by = 'sort', $order = 'asc');
    while ($language = $result->Fetch()) {
        $languages[$language['LID']] = [
            'NAME' => $language['LID'] === 'ru' ? 'Реестр Vercy' : 'Vercy Registry',
            'SECTION_NAME' => $language['LID'] === 'ru' ? 'Разделы' : 'Sections',
            'ELEMENT_NAME' => $language['LID'] === 'ru' ? 'Записи' : 'Records',
        ];
    }
    if ($languages === []) {
        $languages['en'] = ['NAME' => 'Vercy Registry', 'SECTION_NAME' => 'Sections', 'ELEMENT_NAME' => 'Records'];
    }

    $type = new CIBlockType();
    if (!$type->Add([
        'ID' => IBLOCK_TYPE,
        'SECTIONS' => 'Y',
        'IN_RSS' => 'N',
        'SORT' => 100,
        'LANG' => $languages,
    ])) {
        throw bitrixError('Unable to create information block type', $type);
    }
    $CACHE_MANAGER->CleanDir('b_iblock_type');
}

function ensureIblock(string $code, string $name, string $listUrl, string $detailUrl): int
{
    $existing = CIBlock::GetList([], ['TYPE' => IBLOCK_TYPE, '=CODE' => $code])->Fetch();
    $fields = [
        'ACTIVE' => 'Y',
        'NAME' => $name,
        'CODE' => $code,
        'IBLOCK_TYPE_ID' => IBLOCK_TYPE,
        'LID' => ['vc'],
        'SORT' => $code === MODEL_IBLOCK_CODE ? 100 : 200,
        'LIST_PAGE_URL' => $listUrl,
        'DETAIL_PAGE_URL' => $detailUrl,
        'SECTION_PAGE_URL' => '',
        'WORKFLOW' => 'N',
        'BIZPROC' => 'N',
        'GROUP_ID' => ['2' => 'R'],
        'INDEX_ELEMENT' => 'Y',
        'INDEX_SECTION' => 'N',
    ];

    $iblock = new CIBlock();
    if ($existing) {
        $id = (int) $existing['ID'];
        if (!$iblock->Update($id, $fields)) {
            throw bitrixError("Unable to update information block {$code}", $iblock);
        }
        return $id;
    }

    $id = (int) $iblock->Add($fields);
    if ($id <= 0) {
        throw bitrixError("Unable to create information block {$code}", $iblock);
    }
    return $id;
}

function ensureProperties(int $iblockId, array $definitions): void
{
    $sort = 100;
    foreach ($definitions as $code => [$name, $type, $multiple, $filterable]) {
        $priorityWave = (int) ($record['priority_wave'] ?? 9);
        $priorityScore = (int) round((float) ($record['priority_score'] ?? 0));
        $fields = [
            'IBLOCK_ID' => $iblockId,
            'ACTIVE' => 'Y',
            'SORT' => $sort,
            'NAME' => $name,
            'CODE' => $code,
            'PROPERTY_TYPE' => $type,
            'MULTIPLE' => $multiple ? 'Y' : 'N',
            'MULTIPLE_CNT' => 5,
            'FILTRABLE' => $filterable ? 'Y' : 'N',
            'SEARCHABLE' => in_array($code, ['MODEL_ID', 'TAGS', 'ALTERNATE_NAMES', 'NAV_PATH'], true) ? 'Y' : 'N',
        ];
        $existing = CIBlockProperty::GetList([], ['IBLOCK_ID' => $iblockId, 'CODE' => $code])->Fetch();
        $property = new CIBlockProperty();
        if ($existing) {
            if (!$property->Update((int) $existing['ID'], $fields)) {
                throw bitrixError("Unable to update property {$code}", $property);
            }
        } elseif (!$property->Add($fields)) {
            throw bitrixError("Unable to create property {$code}", $property);
        }
        $sort += 10;
    }
}

function sectionCode(string $name): string
{
    $code = strtolower(trim((string) preg_replace('/[^a-zA-Z0-9]+/', '-', $name), '-'));
    return $code !== '' ? $code : 'section-' . substr(sha1($name), 0, 12);
}

function ensureSection(int $iblockId, string $name): int
{
    $code = sectionCode($name);
    $existing = CIBlockSection::GetList([], ['IBLOCK_ID' => $iblockId, 'CODE' => $code], false, ['ID'])->Fetch();
    $section = new CIBlockSection();
    $fields = [
        'IBLOCK_ID' => $iblockId,
        'ACTIVE' => 'Y',
        'NAME' => $name,
        'CODE' => $code,
        'SORT' => 500,
    ];
    if ($existing) {
        $id = (int) $existing['ID'];
        if (!$section->Update($id, $fields)) {
            throw bitrixError("Unable to update section {$name}", $section);
        }
        return $id;
    }
    $id = (int) $section->Add($fields);
    if ($id <= 0) {
        throw bitrixError("Unable to create section {$name}", $section);
    }
    return $id;
}

function propertyValues(array $record, string $batch): array
{
    return [
        'REGISTRY_ID' => $record['registry_id'],
        'MODEL_ID' => $record['model_id'],
        'RECORD_PLANE' => $record['record_plane'],
        'ENTRY_KIND' => $record['entry_kind'],
        'MODEL_STATUS' => $record['status'],
        'STATUS_RAW' => $record['status_raw'],
        'SPEC_AVAILABLE' => $record['spec_available'] ? 'Y' : 'N',
        'VERSION' => $record['version'],
        'FAMILY' => $record['family'],
        'CATEGORY' => $record['category'],
        'INDUSTRY' => $record['industry'],
        'DOMAIN_TAGS' => $record['domain'],
        'TAGS' => $record['tags'],
        'ALTERNATE_NAMES' => $record['alternate_names'],
        'NAV_PATH' => $record['nav_path'],
        'LEGACY_ALIAS' => $record['legacy_alias'],
        'PAGE_URL' => $record['page_url'],
        'SOURCE_URL' => $record['source_url'],
        'SPEC_URL' => $record['spec_url'],
        'AGENTS_URL' => $record['agents_url'],
        'YAML_URL' => $record['yaml_url'],
        'EXISTING_SPEC_REF' => $record['existing_spec_ref'],
        'PARENT_IDS' => $record['parent_ids'],
        'CONTAINS_IDS' => $record['contains_ids'],
        'ALIGNED_IDS' => $record['aligned_model_ids'],
        'OWNER' => $record['owner'],
        'REVIEW_STATE' => $record['review_state'],
        'ORIGIN' => $record['origin'],
        'NAMESPACE_URI' => $record['namespace_uri'],
        'SOURCE_VERSION' => $record['source_version'],
        'SOURCE_GROUP' => $record['source_group'],
        'SOURCE_CATEGORY' => $record['source_category'],
        'SOURCE_FORMAT' => $record['source_format'],
        'COMPOSITION_ROLE' => $record['composition_role'],
        'DEFAULT_LINK_TYPE' => $record['default_link_type'],
        'PRIORITY_WAVE' => $record['priority_wave'],
        'PRIORITY_SCORE' => $record['priority_score'],
        'PRIORITY_CONFIDENCE' => $record['priority_confidence'],
        'PRIORITY_RATIONALE' => $record['priority_rationale'],
        'RELATIONS_REF' => $record['relations_ref'],
        'PROVENANCE' => $record['provenance'],
        'IMPORT_BATCH' => $batch,
    ];
}

function importRecords(int $iblockId, array $records, string $batch, bool $models): array
{
    $seen = [];
    $sections = [];
    $created = 0;
    $updated = 0;

    foreach ($records as $record) {
        $xmlId = (string) $record['registry_id'];
        $seen[$xmlId] = true;
        $sectionName = $models
            ? (string) ($record['category'] ?: 'World model')
            : (string) ($record['source_group'] ?: $record['source_category'] ?: 'Interoperability');
        if (!isset($sections[$sectionName])) {
            $sections[$sectionName] = ensureSection($iblockId, $sectionName);
        }

        $existing = CIBlockElement::GetList(
            [],
            ['IBLOCK_ID' => $iblockId, '=XML_ID' => $xmlId],
            false,
            false,
            ['ID']
        )->Fetch();
        $fields = [
            'IBLOCK_ID' => $iblockId,
            'IBLOCK_SECTION_ID' => $sections[$sectionName],
            'ACTIVE' => 'Y',
            'SORT' => 100 + ($priorityWave * 100) + max(0, 100 - $priorityScore),
            'NAME' => $record['name'],
            'CODE' => $record['code'],
            'XML_ID' => $xmlId,
            'PREVIEW_TEXT_TYPE' => 'text',
            'PREVIEW_TEXT' => $record['purpose'],
            'DETAIL_TEXT_TYPE' => 'text',
            'DETAIL_TEXT' => $record['priority_rationale'],
        ];
        $element = new CIBlockElement();
        if ($existing) {
            $elementId = (int) $existing['ID'];
            if (!$element->Update($elementId, $fields, false, true, true)) {
                throw bitrixError("Unable to update {$xmlId}", $element);
            }
            $updated++;
        } else {
            $elementId = (int) $element->Add($fields, false, true, true);
            if ($elementId <= 0) {
                throw bitrixError("Unable to create {$xmlId}", $element);
            }
            $created++;
        }
        CIBlockElement::SetPropertyValuesEx($elementId, $iblockId, propertyValues($record, $batch));
    }

    $deactivated = 0;
    $existingResult = CIBlockElement::GetList([], ['IBLOCK_ID' => $iblockId, 'ACTIVE' => 'Y'], false, false, ['ID', 'XML_ID']);
    while ($existing = $existingResult->Fetch()) {
        if (!isset($seen[$existing['XML_ID']])) {
            $element = new CIBlockElement();
            if (!$element->Update((int) $existing['ID'], ['ACTIVE' => 'N'])) {
                throw bitrixError("Unable to deactivate stale {$existing['XML_ID']}", $element);
            }
            $deactivated++;
        }
    }

    return ['created' => $created, 'updated' => $updated, 'deactivated' => $deactivated, 'active' => count($records)];
}

try {
    $site = CSite::GetByID('vc')->Fetch();
    if (!$site) {
        throw new RuntimeException('Bitrix site vc is not registered');
    }

    ensureIblockType();
    $modelIblockId = ensureIblock(
        MODEL_IBLOCK_CODE,
        'Vercy Meta-Models',
        '/models/',
        '/models/#ELEMENT_CODE#/'
    );
    $interopIblockId = ensureIblock(
        INTEROP_IBLOCK_CODE,
        'Vercy Interoperability Registry',
        '/registry/interoperability/',
        ''
    );
    ensureProperties($modelIblockId, $propertyDefinitions);
    ensureProperties($interopIblockId, $propertyDefinitions);

    $batch = (string) $payload['generated_at'];
    $modelResult = importRecords($modelIblockId, $payload['models'], $batch, true);
    $interopResult = importRecords($interopIblockId, $payload['interoperability'], $batch, false);
    CIBlock::clearIblockTagCache($modelIblockId);
    CIBlock::clearIblockTagCache($interopIblockId);

    echo json_encode([
        'site' => ['id' => 'vc', 'name' => $site['NAME']],
        'iblocks' => [
            MODEL_IBLOCK_CODE => ['id' => $modelIblockId] + $modelResult,
            INTEROP_IBLOCK_CODE => ['id' => $interopIblockId] + $interopResult,
        ],
        'batch' => $batch,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
} catch (Throwable $exception) {
    fwrite(STDERR, $exception->getMessage() . "\n");
    exit(5);
}
