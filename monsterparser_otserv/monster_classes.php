<?php
class Monster {
    private $name;
    private $experience;
    private $health;
    private $loot;
    private $looktype;

    public function __construct() {
        $this->name = "Undefined";
        $this->experience = 0;
        $this->health = 0;
        $this->loot = array();
        $this->looktype = "Undefined"; // Inicializar $looktype con un valor predeterminado
    }

    public function setName($name) {
        $this->name = $name;
    }

    public function setExperience($experience) {
        $this->experience = $experience;
    }

    public function setHealth($health) {
        $this->health = $health;
    }

    public function setLoot($loot) {
        $this->loot = $loot;
    }

    public function setLooktype($looktype) {
        $this->looktype = $looktype;
    }

    public function getName() {
        return $this->name;
    }

    public function getExperience() {
        return $this->experience;
    }

    public function getHealth() {
        return $this->health;
    }

    public function getLoot() {
        return $this->loot;
    }

    public function getLooktype() {
        return $this->looktype;
    }

    public function addToLoot($item) {
        array_push($this->loot, $item);
    }
}

class Item {
    private $name;
    private $id;
    private $countMax;
    private $chance;
    private $image;

    public function setName($name) {
        $this->name = $name;
    }

    public function setId($id) {
        $this->id = $id;
    }

    public function setCountMax($countMax) {
        $this->countMax = $countMax;
    }

    public function setChance($chance) {
        $this->chance = $chance;
    }

    public function setImage($image) {
        $this->image = $image;
    }

    public function getName() {
        return $this->name;
    }

    public function getId() {
        return $this->id;
    }

    public function getCountMax() {
        return $this->countMax;
    }

    public function getChance() {
        return $this->chance;
    }

    public function getImage() {
        return $this->image;
    }

    public function getChancePercentage() {
        return strval(($this->chance / 1000.0)) . '%';
    }
}
?>