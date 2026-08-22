<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$documentRoot = dirname(__DIR__, 2);
$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'ver.cy';
$_SERVER['SERVER_NAME'] = 'ver.cy';
$_SERVER['REQUEST_URI'] = '/tools/server/inspect-vercy-catalog.php';
define('SITE_ID', 'vc');
define('LANGUAGE_ID', 'en');
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

$result = ['site' => null, 'module' => false, 'type' => null, 'type_db' => null, 'iblocks' => []];
$site = CSite::GetByID('vc')->Fetch();
$result['site'] = $site ? ['id' => $site['LID'], 'name' => $site['NAME'], 'dir' => $site['DIR']] : null;
$result['module'] = (bool) CModule::IncludeModule('iblock');
if ($result['module']) {
    global $DB;
    $type = CIBlockType::GetByID('vercy_registry')->Fetch();
    $result['type'] = $type ?: null;
    $typeDb = $DB->Query("SELECT * FROM b_iblock_type WHERE ID='vercy_registry'")->Fetch();
    $result['type_db'] = $typeDb ?: null;
    $iblocks = CIBlock::GetList(['ID' => 'ASC'], ['TYPE' => 'vercy_registry']);
    while ($iblock = $iblocks->Fetch()) {
        $count = CIBlockElement::GetList([], ['IBLOCK_ID' => (int) $iblock['ID']], [], false, ['ID']);
        $result['iblocks'][] = [
            'id' => (int) $iblock['ID'],
            'code' => $iblock['CODE'],
            'name' => $iblock['NAME'],
            'active' => $iblock['ACTIVE'],
            'elements' => (int) $count,
            'properties' => (int) ($DB->Query('SELECT COUNT(*) C FROM b_iblock_property WHERE IBLOCK_ID=' . (int) $iblock['ID'])->Fetch()['C'] ?? 0),
            'property_values' => (int) ($DB->Query('SELECT COUNT(*) C FROM b_iblock_element_property P INNER JOIN b_iblock_element E ON E.ID=P.IBLOCK_ELEMENT_ID WHERE E.IBLOCK_ID=' . (int) $iblock['ID'])->Fetch()['C'] ?? 0),
        ];
    }
}
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
