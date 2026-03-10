<?php 
###### MONSTER LOOT CHECKER ######
###### VERSION: 1.5

echo "(0) starting ";
require_once('monster_classes.php');
require_once('config.php'); // Añadir la configuración

/* CONFIG */
$data_location = 'C:/Users/felip/Documents/GitHub/pro-ot/data';
$monster_dir = '/monsters/';
$items_dir = '/items/';
$monsters_file = 'monsters.xml';
$items_file = 'items.xml';
$cache_dir = 'monsters';
$image_dir = 'C:/xampp/htdocs/layout/monster_loot_img/';
$image_url_dir = '/layout/monster_loot_img/'; // Web-accessible path to images
/* CONFIG */

if (file_exists($cache_dir)) {
    echo "(1) cache exists ";
} else {
    if (mkdir($cache_dir, 0777, true)) {
        echo "(2) mkdir done ";
    } else {
        die("Error: Could not create cache directory");
    }
}

$items_loaded = array();
$items_xml_path = $data_location . $items_dir . $items_file;
if (file_exists($items_xml_path)) {
    $items_xml = simplexml_load_file($items_xml_path);
    if ($items_xml === false) {
        die('Error: Could not load items.xml');
    }
    echo "(3) loaded items.xml ";
} else {
    die("Error: items.xml file does not exist at $items_xml_path");
}

foreach ($items_xml->children() as $item) {
    if (empty(strval($item['fromid']))) {
        $items_loaded[(int)strval($item['id'])] = strval($item['name']);
        continue;
    }
    $fromid = (int) strval($item['fromid']);
    $toid = (int) strval($item['toid']);
    for ($i = $fromid; $i <= $toid; $i++) {
        $items_loaded[$i] = strval($item['name']);
    }
}
echo "(4) loaded items ";

$monsters_xml_path = $data_location . $monster_dir . $monsters_file;
if (file_exists($monsters_xml_path)) {
    $monsters_xml = simplexml_load_file($monsters_xml_path);
    if ($monsters_xml === false) {
        die('Error: Could not load monsters.xml');
    }
    echo "(5) loaded monsters.xml ";
} else {
    die("Error: monsters.xml file does not exist at $monsters_xml_path");
}

$monsters_paths = array();
foreach ($monsters_xml->children() as $monster) {
    $monster_file_path = $data_location . $monster_dir . $monster['file'];
    if (file_exists($monster_file_path)) {
        array_push($monsters_paths, $monster_file_path);
    } else {
        echo "Warning: Monster file does not exist at $monster_file_path\n";
    }
}
echo "(6) loaded monsters paths ";

$monsters_loaded = array();
foreach ($monsters_paths as $monster_path) {
    $monster_xml = simplexml_load_file($monster_path);
    if ($monster_xml === false) {
        echo "Warning: Could not load monster file at $monster_path\n";
        continue;
    }
    $monster = new Monster();
    $basename = basename($monster_path, '.xml');
    $basename = str_replace('_', " ", $basename);
    $monster->setName($basename);
    $monster->setExperience((int)strval($monster_xml['experience']));
    $monster->setHealth((int)strval($monster_xml->health['max']));

    $looktype_value = 0;
    if (isset($monster_xml->look['type'])) {
        $looktype_value = (int)strval($monster_xml->look['type']);
    }
    $monster->setLooktype($looktype_value);

    if ($monster_xml->loot->item == null) {
        array_push($monsters_loaded, $monster);
        continue;
    }
    foreach ($monster_xml->loot->item as $item) {
        $item_o = new Item();
        if (!empty(strval($item['name']))) {
            $item_o->setName(strval($item['name']));
        }
        if (!empty(strval($item['id']))) {
            $offset = (int)strval($item['id']);
            if (array_key_exists($offset, $items_loaded)) {
                $item_o->setName($items_loaded[$offset]);
                $item_o->setImage($image_url_dir . $offset . '.gif'); // Set the web-accessible image path
            }
        }
        if (!empty(strval($item['countmax']))) {
            $item_o->setCountMax((int)strval($item['countmax']));
        }
        if (!empty(strval($item['chance']))) {
            $item_o->setChance((int)strval($item['chance']));
        }
        $monster->addToLoot($item_o);
    }
    array_push($monsters_loaded, $monster);
}
echo "(7) monster classes done ";

foreach ($monsters_loaded as $monster) {
    $cache_file = fopen($cache_dir . '/' . $monster->getName() . '.cache', "w");
    fwrite($cache_file, serialize($monster));
    fclose($cache_file);
}
echo "(8) cache files done ";

// Display the monsters and their loot with images
foreach ($monsters_loaded as $monster) {
    echo "<h2>Monster: " . htmlspecialchars($monster->getName()) . "</h2>";
    echo "<p>Experience: " . htmlspecialchars($monster->getExperience()) . "</p>";
    echo "<p>Health: " . htmlspecialchars($monster->getHealth()) . "</p>";
    echo "<p>Looktype: " . htmlspecialchars($monster->getLooktype()) . "</p>";

    // Show the outfit image
    if ($monster->getLooktype() > 0) {
        echo "<p><img src='{$config['show_outfits']['imageServer']}?id={$monster->getLooktype()}' alt='Outfit' /></p>";
    }

    echo "<h3>Loot:</h3>";
    echo "<ul>";
    foreach ($monster->getLoot() as $loot_item) {
        echo "<li>";
        if ($loot_item->getImage()) {
            echo "<img src='" . htmlspecialchars($loot_item->getImage()) . "' alt='" . htmlspecialchars($loot_item->getName()) . "' />";
        }
        echo htmlspecialchars($loot_item->getName()) . " (Max Count: " . htmlspecialchars($loot_item->getCountMax()) . ", Chance: " . htmlspecialchars($loot_item->getChance()) . "%)";
        echo "</li>";
    }
    echo "</ul>";
}
?>
