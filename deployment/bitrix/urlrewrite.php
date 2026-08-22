<?php
$arUrlRewrite = [
    [
        'CONDITION' => '#^/models/([^/]+)/?$#',
        'RULE' => 'model=$1',
        'ID' => '',
        'PATH' => '/models/index.php',
        'SORT' => 100,
    ],
];
