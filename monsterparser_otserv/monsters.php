<?php
require_once 'engine/init.php'; 
require_once 'config.php';
include 'layout/overall/header.php'; 
?>
<style>
    .bold-text {
        font-weight: bold;
    }
    .monster-name {
        font-weight: bold;
        text-decoration: none; /* This removes the underline from links */
        color: blue; /* This sets the color to blue */
    }

    .monster-name:hover {
        text-decoration: underline; /* This adds an underline when you hover over the link */
    }

    .table-container {
        max-width: 900px;
        margin: 20px auto;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
    }
    th, td {
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #faf0d7;
    }
    th {
        background-color: #A9A9A9;
        color: white;
    }
    td img {
        max-width: 50px;
        max-height: 50px;
        vertical-align: middle;
        margin-right: 10px;
    }
    /* Apply hover effect to table rows */
    .table-container table tr.highlight:hover {
        background-color: #f2f2f2;
        cursor: pointer;
    }
</style>



<?php
function getMonsterFromCache($monsterName) {
    global $cache_dir, $data_location, $monster_dir;
    $cacheFile = $cache_dir . '/' . $monsterName . '.cache';
    if (file_exists($cacheFile)) {
        return unserialize(file_get_contents($cacheFile));
    } else {
        // If cache doesn't exist, let's try to get some basic info from the XML
        $monster = new Monster();
        $monster->setName($monsterName);

        $xmlFile = $data_location . $monster_dir . str_replace(' ', '_', $monsterName) . '.xml';
        if (file_exists($xmlFile)) {
            $xml = simplexml_load_file($xmlFile);
            if ($xml !== false) {
                $looktype = isset($xml->look['type']) ? (int)$xml->look['type'] : (isset($xml->look['typeex']) ? (int)$xml->look['typeex'] : 0);
                $monster->setLooktype($looktype);
            }
        }

        return $monster;
    }
}  

require_once('monster_classes.php');
$cache_dir = 'monsters';
if (isset($_GET['name'])) {
    $file_path = $cache_dir . '/' . $_GET['name'] . '.cache';
    if (file_exists($file_path)) {
        $serialized = file_get_contents($file_path);
        $monster = unserialize($serialized);
        $name = $monster->getName();
        $health = $monster->getHealth();
        $experience = $monster->getExperience();
        $looktype = $monster->getLooktype();
?>
        <div class="table-container">
            <div class="TableContainer">
                <div class="CaptionContainer">
                    <div class="CaptionInnerContainer">
                        <span class="CaptionEdgeLeftTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionEdgeRightTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionBorderTop" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                        <span class="CaptionVerticalLeft" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                        <div class="Text">Monster Stats: <?php echo $name; ?></div>
                        <span class="CaptionVerticalRight" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                        <span class="CaptionBorderBottom" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                        <span class="CaptionEdgeLeftBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionEdgeRightBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                    </div>
                </div>
                <table class="Table3" cellspacing="0" cellpadding="0">
                    <tbody>
                        <tr>
                            <td>
                                <div class="InnerTableContainer">
                                    <table style="width:100%;">
                                        <tr>
                                            <td>
                                                <div class="TableShadowContainerRightTop">
                                                    <div class="TableShadowRightTop" style="background-image:url(layout/tibia_img/table-shadow-rt.gif);"></div>
                                                </div>
                                                <div class="TableContentAndRightShadow" style="background-image:url(layout/tibia_img/table-shadow-rm.gif);">
                                                    <div class="TableContentContainer">
                                                        <table class="TableContent" width="100%" style="border:1px solid #faf0d7;">
                                                            <tr>
                                                                <th>Name</th>
                                                                <th>Health</th>
                                                                <th>Experience</th>
                                                                <th>Looktype</th>
                                                            </tr>
                                                            <tr class="highlight"> <!-- Add highlight class for hover effect -->
                                                             <td><?php echo '<b>' . $name . '</b>'; ?></td>
<td><?php echo '<b>' . $health . '</b>'; ?></td>
<td><?php echo '<b>' . $experience . '</b>'; ?></td>
                                                                <td>
                                                                    <?php if ($looktype > 0): ?>
                                                                        <img src="<?php echo $config['show_outfits']['imageServer']; ?>?id=<?php echo $looktype; ?>" alt="Outfit" />
                                                                    <?php endif; ?>
                                                                </td>
                                                            </tr>
                                                        </table>
                                                    </div>
                                                </div>
                                                <div class="TableShadowContainer">
                                                    <div class="TableBottomShadow" style="background-image:url(layout/tibia_img/table-shadow-bm.gif);">
                                                        <div class="TableBottomLeftShadow" style="background-image:url(layout/tibia_img/table-shadow-bl.gif);"></div>
                                                        <div class="TableBottomRightShadow" style="background-image:url(layout/tibia_img/table-shadow-br.gif);"></div>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="table-container">
            <div class="TableContainer">
                <div class="CaptionContainer">
                    <div class="CaptionInnerContainer">
                        <span class="CaptionEdgeLeftTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionEdgeRightTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionBorderTop" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                        <span class="CaptionVerticalLeft" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                        <div class="Text">Monster Loot</div>
                        <span class="CaptionVerticalRight" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                        <span class="CaptionBorderBottom" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                        <span class="CaptionEdgeLeftBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                        <span class="CaptionEdgeRightBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                    </div>
                </div>
                <table class="Table3" cellspacing="0" cellpadding="0">
                    <tbody>
                        <tr>
                            <td>
                                <div class="InnerTableContainer">
                                    <table style="width:100%;">
                                        <tr>
                                            <td>
                                                <div class="TableShadowContainerRightTop">
                                                    <div class="TableShadowRightTop" style="background-image:url(layout/tibia_img/table-shadow-rt.gif);"></div>
                                                </div>
                                                <div class="TableContentAndRightShadow" style="background-image:url(layout/tibia_img/table-shadow-rm.gif);">
                                                    <div class="TableContentContainer">
                                                        <table class="TableContent" width="100%" style="border:1px solid #faf0d7;">
                                                            <tr>
                                                                <th>Item</th>
                                                                <th>Max</th>
                                                                <th>Chance</th>
                                                            </tr>
                                                            <?php foreach ($monster->getLoot() as $item): ?>
                                                            <tr class="highlight"> <!-- Add highlight class for hover effect -->
                                                                <td>
  <?php if ($item->getImage()): ?>
    <img src="<?php echo htmlspecialchars($item->getImage()); ?>" alt="<?php echo htmlspecialchars($item->getName()); ?>" />
<?php endif; ?>
<strong><?php echo '<b>' . htmlspecialchars($item->getName()) . '</b>'; ?></strong>
</td>
<td><?php echo '<b>' . (($item->getCountMax() == 0) ? 1 : $item->getCountMax()) . '</b>'; ?></td>
<td><?php echo '<b>' . $item->getChancePercentage() . '</b>'; ?></td>



                                                            </tr>
                                                            <?php endforeach; ?>
                                                        </table>
                                                    </div>
                                                </div>
                                                <div class="TableShadowContainer">
                                                    <div class="TableBottomShadow" style="background-image:url(layout/tibia_img/table-shadow-bm.gif);">
                                                        <div class="TableBottomLeftShadow" style="background-image:url(layout/tibia_img/table-shadow-bl.gif);"></div>
                                                        <div class="TableBottomRightShadow" style="background-image:url(layout/tibia_img/table-shadow-br.gif);"></div>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
<?php
    }
}
if (!isset($_GET['name'])) {
    showList($cache_dir);
}
function showList($cache_dir) {
    $scan = scandir($cache_dir);
    $monsters = array();
    foreach($scan as $file) {
        if (strpos($file, '.cache') != false) {
            $monsters[] = str_replace('.cache', '', $file);
        }
    }
    $page_i = 0;
    $previous_page = 0;
    $get_page = 0;
    $next_page = 1;
    $last_page = false;
    $per_page = 40;
    if (isset($_GET['page'])) {
        $page_i = $_GET['page'] * $per_page;
        $get_page = $_GET['page'];
        $previous_page = $_GET['page'] - 1;
        if ($get_page == 0) {
            $previous_page = 0;
        }
        $next_page = $_GET['page'] + 1;
    }
?>
    <div class="table-container">
        <div class="TableContainer">
            <div class="CaptionContainer">
                <div class="CaptionInnerContainer">
                    <span class="CaptionEdgeLeftTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                    <span class="CaptionEdgeRightTop" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                    <span class="CaptionBorderTop" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                    <span class="CaptionVerticalLeft" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                    <div class="Text">Monster List</div>
                    <span class="CaptionVerticalRight" style="background-image:url(layout/tibia_img/box-frame-vertical.gif);"></span>
                    <span class="CaptionBorderBottom" style="background-image:url(layout/tibia_img/table-headline-border.gif);"></span>
                    <span class="CaptionEdgeLeftBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                    <span class="CaptionEdgeRightBottom" style="background-image:url(layout/tibia_img/box-frame-edge.gif);"></span>
                </div>
            </div>
            <table class="Table3" cellspacing="0" cellpadding="0">
                <tbody>
                    <tr>
                        <td>
                            <div class="InnerTableContainer">
                                <table style="width:100%;">
                                    <tr>
                                        <td>
                                            <div class="TableShadowContainerRightTop">
                                                <div class="TableShadowRightTop" style="background-image:url(layout/tibia_img/table-shadow-rt.gif);"></div>
                                            </div>
                                            <div class="TableContentAndRightShadow" style="background-image:url(layout/tibia_img/table-shadow-rm.gif);">
                                                <div class="TableContentContainer">
                                                    <table class="TableContent" width="100%" style="border:1px solid #faf0d7;">
<?php for ($i = $page_i; $i < $page_i + $per_page; $i++): ?>
    <?php if (!isset($monsters[$i])): ?>
        <?php $last_page = true; break; ?>
    <?php endif; ?>
    <?php 
    $monster = getMonsterFromCache($monsters[$i]);
    $looktype = $monster->getLooktype(); 
    echo "<!-- Debug: Monster: " . htmlspecialchars($monsters[$i]) . ", Looktype: " . htmlspecialchars($looktype) . " -->";
    ?>
    <tr class="highlight">
        <td>
            <a href="?name=<?php echo $monsters[$i]; ?>" class="monster-name"><?php echo $monsters[$i]; ?></a>
        </td>
        <td>
            <?php if ($looktype > 0): ?>
                <?php 
                $imageServer = isset($config['show_outfits']['imageServer']) ? $config['show_outfits']['imageServer'] : 'http://outfit-images.ots.me/outfit.php';
                $imageUrl = $imageServer . '?id=' . $looktype; 
                ?>
                <img src="<?php echo $imageUrl; ?>" alt="Outfit" />
                <!-- Debug: Image URL: <?php echo htmlspecialchars($imageUrl); ?> -->
            <?php endif; ?>
        </td>
    </tr>
<?php endfor; ?>
</table>

                                                    <!-- <table class="TableContent" width="100%" style="border:1px solid #faf0d7;"> -->
                                                        <!-- <php for ($i = $page_i; $i < $page_i+$per_page; $i++): ?> -->
                                                            <!-- <php if (!isset($monsters[$i])): ?> -->
                                                                <!-- <php $last_page = true; break; ?> -->
                                                            <!-- <php endif; ?> -->
                                                            <!-- <tr class="highlight">  Add highlight class for hover effect --> -->
                                                                <!-- <td><a href="?name=<php echo $monsters[$i]; ?>"><php echo $monsters[$i]; ?></a></td> -->
                                                            <!-- </tr> -->
                                                        <!-- <php endfor; ?> -->
                                                    <!-- </table> -->
                                                </div>
                                            </div>
                                           <div class="TableShadowContainer">
                <div class="TableBottomShadow" style="background-image:url(layout/tibia_img/table-shadow-bm.gif);">
                    <div class="TableBottomLeftShadow" style="background-image:url(layout/tibia_img/table-shadow-bl.gif);"></div>
                    <div class="TableBottomRightShadow" style="background-image:url(layout/tibia_img/table-shadow-br.gif);"></div>
                </div>
            </div>
        </div>
    </div>
    <div style="text-align: center; margin: 20px 0;">
        <?php if ($previous_page != $get_page): ?>
            <a style="font-size:32px; margin-right: 20px;" href="?page=<?php echo $previous_page; ?>">🡐</a>
        <?php endif; ?>
        <?php if (!$last_page): ?>
            <a style="font-size:32px;" href="?page=<?php echo $next_page; ?>">🡒</a>
        <?php endif; ?>
    </div>
<?php
}
?>
