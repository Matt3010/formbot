<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        if (!Schema::hasTable('form_definitions') || Schema::hasColumn('form_definitions', 'ai_confidence')) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) {
            $table->decimal('ai_confidence', 3, 2)->nullable();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        if (!Schema::hasTable('form_definitions') || !Schema::hasColumn('form_definitions', 'ai_confidence')) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) {
            $table->dropColumn('ai_confidence');
        });
    }
};
