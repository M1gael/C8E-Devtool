<?php

use Tina4\ORM;

class ActivityLog extends ORM
{
    public string $tableName = "activity_logs";
    public string $primaryKey = "id";
    public bool $autoMap = true;

    public int $id;
    public int $userId;
    public string $action;
    public string $entityType;
    public int $entityId;
    public ?string $details = null;
    public string $createdAt;

    /**
     * Get the staff user who made the change
     * @return User|null
     */
    public function user(): ?User
    {
        return $this->belongsTo(User::class, "user_id");
    }
}
