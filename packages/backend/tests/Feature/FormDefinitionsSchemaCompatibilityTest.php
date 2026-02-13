<?php

namespace Tests\Feature;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class FormDefinitionsSchemaCompatibilityTest extends TestCase
{
    use RefreshDatabase;

    private function migration(): object
    {
        return require database_path('migrations/2024_01_01_000013_add_ai_confidence_to_form_definitions_table.php');
    }

    public function test_migration_adds_ai_confidence_when_missing(): void
    {
        $this->assertTrue(Schema::hasColumn('form_definitions', 'ai_confidence'));

        Schema::table('form_definitions', function (Blueprint $table) {
            $table->dropColumn('ai_confidence');
        });

        $this->assertFalse(Schema::hasColumn('form_definitions', 'ai_confidence'));

        $this->migration()->up();

        $this->assertTrue(Schema::hasColumn('form_definitions', 'ai_confidence'));
    }

    public function test_migration_is_idempotent_when_column_exists(): void
    {
        $this->assertTrue(Schema::hasColumn('form_definitions', 'ai_confidence'));

        $this->migration()->up();

        $this->assertTrue(Schema::hasColumn('form_definitions', 'ai_confidence'));
    }
}
