<?php

namespace Tests\Feature;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class FormDefinitionsLegacySchemaRepairTest extends TestCase
{
    use RefreshDatabase;

    private function repairMigration(): object
    {
        return require database_path('migrations/2024_01_01_000014_repair_form_definitions_legacy_columns.php');
    }

    private function assertColumnsExist(): void
    {
        $this->assertTrue(Schema::hasColumn('form_definitions', 'ai_confidence'));
        $this->assertTrue(Schema::hasColumn('form_definitions', 'captcha_detected'));
        $this->assertTrue(Schema::hasColumn('form_definitions', 'two_factor_expected'));
        $this->assertTrue(Schema::hasColumn('form_definitions', 'human_breakpoint'));
    }

    private function assertColumnsMissing(): void
    {
        $this->assertFalse(Schema::hasColumn('form_definitions', 'ai_confidence'));
        $this->assertFalse(Schema::hasColumn('form_definitions', 'captcha_detected'));
        $this->assertFalse(Schema::hasColumn('form_definitions', 'two_factor_expected'));
        $this->assertFalse(Schema::hasColumn('form_definitions', 'human_breakpoint'));
    }

    private function dropColumn(string $column): void
    {
        if (!Schema::hasColumn('form_definitions', $column)) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) use ($column) {
            $table->dropColumn($column);
        });
    }

    public function test_repair_migration_restores_all_legacy_missing_columns(): void
    {
        $this->assertColumnsExist();

        $this->dropColumn('ai_confidence');
        $this->dropColumn('captcha_detected');
        $this->dropColumn('two_factor_expected');
        $this->dropColumn('human_breakpoint');

        $this->assertColumnsMissing();

        $this->repairMigration()->up();

        $this->assertColumnsExist();
    }

    public function test_repair_migration_is_idempotent(): void
    {
        $this->assertColumnsExist();

        $this->repairMigration()->up();
        $this->repairMigration()->up();

        $this->assertColumnsExist();
    }
}
