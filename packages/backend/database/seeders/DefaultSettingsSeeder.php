<?php

namespace Database\Seeders;

use App\Models\AppSetting;
use Illuminate\Database\Seeder;

class DefaultSettingsSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $defaults = [
            'max_parallel_global' => '5',
            'retention_days' => '30',
            'default_action_delay_ms' => '500',
        ];

        foreach ($defaults as $key => $value) {
            AppSetting::firstOrCreate(
                ['key' => $key],
                ['value' => $value, 'updated_at' => now()]
            );
        }
    }
}
