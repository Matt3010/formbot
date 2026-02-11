<?php

namespace Tests\Feature;

use App\Models\ExecutionLog;
use App\Models\Task;
use App\Models\User;
use App\Services\ScraperClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Laravel\Passport\Passport;
use Mockery;
use Tests\TestCase;

class ExecutionTest extends TestCase
{
    use RefreshDatabase;

    private User $user;
    private Task $task;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);

        $this->task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'active',
        ]);
    }

    private function createExecution(array $overrides = []): ExecutionLog
    {
        return ExecutionLog::create(array_merge([
            'task_id' => $this->task->id,
            'started_at' => now()->subMinutes(5),
            'status' => 'success',
            'is_dry_run' => false,
            'retry_count' => 0,
        ], $overrides));
    }

    // -----------------------------------------------------------------
    // List executions for a task
    // -----------------------------------------------------------------

    public function test_list_executions_for_a_task(): void
    {
        $exec1 = $this->createExecution([
            'status' => 'success',
            'completed_at' => now()->subMinutes(2),
        ]);
        $exec2 = $this->createExecution([
            'status' => 'failed',
            'error_message' => 'Timeout',
            'completed_at' => now()->subMinute(),
        ]);
        $exec3 = $this->createExecution([
            'status' => 'running',
        ]);

        $response = $this->getJson("/api/tasks/{$this->task->id}/executions");

        $response->assertStatus(200)
            ->assertJsonCount(3, 'data')
            ->assertJsonStructure([
                'data' => [
                    '*' => [
                        'id', 'task_id', 'started_at', 'completed_at',
                        'status', 'is_dry_run', 'retry_count',
                        'error_message', 'screenshot_path', 'steps_log',
                        'vnc_session_id', 'created_at', 'updated_at',
                    ],
                ],
            ]);

        // Should be ordered by created_at desc -- most recent first
        $statuses = collect($response->json('data'))->pluck('status')->all();
        $this->assertEquals($exec3->id, $response->json('data.0.id'));
    }

    public function test_list_executions_does_not_show_other_users_task_executions(): void
    {
        $otherUser = User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);

        $otherTask = Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);

        ExecutionLog::create([
            'task_id' => $otherTask->id,
            'started_at' => now(),
            'status' => 'running',
        ]);

        $response = $this->getJson("/api/tasks/{$otherTask->id}/executions");

        $response->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // Get single execution detail
    // -----------------------------------------------------------------

    public function test_get_single_execution_detail(): void
    {
        $execution = $this->createExecution([
            'status' => 'success',
            'completed_at' => now(),
            'steps_log' => [
                ['step' => 1, 'action' => 'navigate', 'url' => 'https://example.com'],
                ['step' => 2, 'action' => 'fill', 'field' => 'username'],
            ],
        ]);

        $response = $this->getJson("/api/executions/{$execution->id}");

        $response->assertStatus(200)
            ->assertJsonPath('data.id', $execution->id)
            ->assertJsonPath('data.task_id', $this->task->id)
            ->assertJsonPath('data.status', 'success')
            ->assertJsonPath('data.steps_log.0.action', 'navigate')
            ->assertJsonPath('data.steps_log.1.action', 'fill')
            // Task should be loaded as a relation
            ->assertJsonStructure([
                'data' => [
                    'id', 'task_id', 'status', 'steps_log',
                    'task' => ['id', 'name'],
                ],
            ]);
    }

    public function test_get_execution_for_another_users_task_returns_403(): void
    {
        $otherUser = User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);

        $otherTask = Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);

        $execution = ExecutionLog::create([
            'task_id' => $otherTask->id,
            'started_at' => now(),
            'status' => 'running',
        ]);

        $response = $this->getJson("/api/executions/{$execution->id}");

        $response->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // Resume execution
    // -----------------------------------------------------------------

    public function test_resume_execution_calls_scraper(): void
    {
        $execution = $this->createExecution([
            'status' => 'waiting_manual',
            'vnc_session_id' => 'vnc-session-123',
        ]);

        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('resumeVnc')
            ->once()
            ->with('vnc-session-123', (string) $execution->id)
            ->andReturn(['status' => 'resumed', 'message' => 'Session resumed']);

        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $response = $this->postJson("/api/executions/{$execution->id}/resume");

        $response->assertStatus(200)
            ->assertJsonPath('status', 'resumed')
            ->assertJsonPath('message', 'Session resumed');
    }

    public function test_resume_execution_fails_without_vnc_session(): void
    {
        $execution = $this->createExecution([
            'status' => 'running',
            'vnc_session_id' => null,
        ]);

        $response = $this->postJson("/api/executions/{$execution->id}/resume");

        $response->assertStatus(400)
            ->assertJsonPath('message', 'No VNC session for this execution.');
    }

    // -----------------------------------------------------------------
    // Abort execution
    // -----------------------------------------------------------------

    public function test_abort_execution_with_vnc_session(): void
    {
        $execution = $this->createExecution([
            'status' => 'running',
            'vnc_session_id' => 'vnc-session-456',
        ]);

        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('stopVnc')
            ->once()
            ->with('vnc-session-456')
            ->andReturn(['status' => 'stopped']);

        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $response = $this->postJson("/api/executions/{$execution->id}/abort");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Execution aborted.');

        $execution->refresh();
        $this->assertEquals('failed', $execution->status);
        $this->assertEquals('Aborted by user', $execution->error_message);
        $this->assertNotNull($execution->completed_at);
    }

    public function test_abort_execution_without_vnc_session(): void
    {
        $execution = $this->createExecution([
            'status' => 'running',
            'vnc_session_id' => null,
        ]);

        $response = $this->postJson("/api/executions/{$execution->id}/abort");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Execution aborted.');

        $execution->refresh();
        $this->assertEquals('failed', $execution->status);
        $this->assertEquals('Aborted by user', $execution->error_message);
    }

    // -----------------------------------------------------------------
    // Logs endpoint (recent executions across all tasks)
    // -----------------------------------------------------------------

    public function test_logs_endpoint_returns_executions_for_current_user(): void
    {
        $this->createExecution(['status' => 'success']);
        $this->createExecution(['status' => 'failed']);

        // Create execution for another user
        $otherUser = User::create([
            'name' => 'Other',
            'email' => 'other@example.com',
            'password' => bcrypt('password'),
        ]);
        $otherTask = Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);
        ExecutionLog::create([
            'task_id' => $otherTask->id,
            'started_at' => now(),
            'status' => 'success',
        ]);

        $response = $this->getJson('/api/logs');

        $response->assertStatus(200)
            ->assertJsonCount(2, 'data');
    }

    // -----------------------------------------------------------------
    // File upload
    // -----------------------------------------------------------------

    public function test_upload_file(): void
    {
        $file = \Illuminate\Http\UploadedFile::fake()->create('document.pdf', 500);

        $response = $this->postJson('/api/files/upload', [
            'file' => $file,
        ]);

        $response->assertStatus(200)
            ->assertJsonStructure(['path', 'filename']);

        $this->assertNotEmpty($response->json('path'));
        $this->assertNotEmpty($response->json('filename'));
    }

    public function test_upload_file_validation_requires_file(): void
    {
        $response = $this->postJson('/api/files/upload', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['file']);
    }
}
