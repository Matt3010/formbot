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
        Schema::table('form_definitions', function (Blueprint $table) {
            if (!Schema::hasColumn('form_definitions', 'human_breakpoint')) {
                $table->boolean('human_breakpoint')->default(false)->after('submit_selector');
            }

            if (Schema::hasColumn('form_definitions', 'ai_confidence')) {
                $table->dropColumn('ai_confidence');
            }

            if (Schema::hasColumn('form_definitions', 'captcha_detected')) {
                $table->dropColumn('captcha_detected');
            }

            if (Schema::hasColumn('form_definitions', 'two_factor_expected')) {
                $table->dropColumn('two_factor_expected');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('form_definitions', function (Blueprint $table) {
            if (!Schema::hasColumn('form_definitions', 'ai_confidence')) {
                $table->decimal('ai_confidence', 3, 2)->nullable()->after('submit_selector');
            }

            if (!Schema::hasColumn('form_definitions', 'captcha_detected')) {
                $table->boolean('captcha_detected')->default(false)->after('ai_confidence');
            }

            if (!Schema::hasColumn('form_definitions', 'two_factor_expected')) {
                $table->boolean('two_factor_expected')->default(false)->after('captcha_detected');
            }
        });
    }
};
