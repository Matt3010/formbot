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
        if (!Schema::hasTable('form_definitions')) {
            return;
        }

        $needsAiConfidence = !Schema::hasColumn('form_definitions', 'ai_confidence');
        $needsCaptchaDetected = !Schema::hasColumn('form_definitions', 'captcha_detected');
        $needsTwoFactorExpected = !Schema::hasColumn('form_definitions', 'two_factor_expected');
        $needsHumanBreakpoint = !Schema::hasColumn('form_definitions', 'human_breakpoint');

        if (!$needsAiConfidence && !$needsCaptchaDetected && !$needsTwoFactorExpected && !$needsHumanBreakpoint) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) use (
            $needsAiConfidence,
            $needsCaptchaDetected,
            $needsTwoFactorExpected,
            $needsHumanBreakpoint
        ) {
            if ($needsAiConfidence) {
                $table->decimal('ai_confidence', 3, 2)->nullable();
            }

            if ($needsCaptchaDetected) {
                $table->boolean('captcha_detected')->default(false);
            }

            if ($needsTwoFactorExpected) {
                $table->boolean('two_factor_expected')->default(false);
            }

            if ($needsHumanBreakpoint) {
                $table->boolean('human_breakpoint')->default(false);
            }
        });
    }

    /**
     * Reverse the migrations.
     *
     * This migration repairs legacy schemas and intentionally does not
     * remove columns on rollback.
     */
    public function down(): void
    {
        // No-op on purpose.
    }
};
