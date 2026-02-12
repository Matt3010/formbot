<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('analyses', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->text('url');
            $table->text('target_url')->nullable();
            $table->text('login_url')->nullable();
            $table->enum('type', ['simple', 'login_and_target', 'next_page']);
            $table->enum('status', ['pending', 'analyzing', 'completed', 'failed', 'cancelled', 'timed_out'])->default('pending');
            $table->jsonb('result')->nullable();
            $table->text('error')->nullable();
            $table->string('model', 100)->nullable();
            $table->uuid('task_id')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->timestamps();

            $table->index(['user_id', 'status']);
            $table->index('created_at');
            $table->foreign('task_id')->references('id')->on('tasks')->nullOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('analyses');
    }
};
