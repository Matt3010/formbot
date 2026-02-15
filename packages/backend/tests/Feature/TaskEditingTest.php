<?php

namespace Tests\Feature;

use App\Models\Task;
use App\Models\User;
use App\Services\ScraperClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Laravel\Passport\Passport;
use Mockery;
use Tests\TestCase;

class TaskEditingTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);
    }

    // -----------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------

    private function createTask(array $overrides = []): Task
    {
        return Task::create(array_merge([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'editing',
            'editing_status' => 'idle',
        ], $overrides));
    }

    private function createOtherUser(): User
    {
        return User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);
    }

    // -----------------------------------------------------------------
    // POST /api/analyze — Task creation for editing
    // -----------------------------------------------------------------

    public function test_analyze_creates_task_with_editing_status(): void
    {
        $response = $this->postJson('/api/analyze', [
            'url' => 'https://example.com/form',
            'name' => 'My Task',
        ]);

        $response->assertStatus(200)
            ->assertJsonStructure(['task_id', 'message']);

        $taskId = $response->json('task_id');

        $this->assertDatabaseHas('tasks', [
            'id' => $taskId,
            'user_id' => $this->user->id,
            'name' => 'My Task',
            'target_url' => 'https://example.com/form',
            'status' => 'editing',
            'editing_status' => 'idle',
        ]);

        // Verify user_corrections contains initial step structure
        $task = Task::find($taskId);
        $this->assertNotNull($task->user_corrections);
        $this->assertArrayHasKey('steps', $task->user_corrections);
        $this->assertCount(1, $task->user_corrections['steps']);
        $this->assertEquals('target', $task->user_corrections['steps'][0]['form_type']);
    }

    public function test_analyze_uses_default_name_if_not_provided(): void
    {
        $response = $this->postJson('/api/analyze', [
            'url' => 'https://example.com/form',
        ]);

        $response->assertStatus(200);
        $taskId = $response->json('task_id');

        $this->assertDatabaseHas('tasks', [
            'id' => $taskId,
            'name' => 'New Task',
        ]);
    }

    public function test_analyze_validates_url_required(): void
    {
        $response = $this->postJson('/api/analyze', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['url']);
    }

    public function test_analyze_validates_url_format(): void
    {
        $response = $this->postJson('/api/analyze', [
            'url' => 'not-a-valid-url',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['url']);
    }

    // -----------------------------------------------------------------
    // POST /api/tasks/{task}/editing/start — Start VNC editing
    // -----------------------------------------------------------------

    public function test_start_editing_session(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('startInteractiveTask')
            ->once()
            ->andReturn(['status' => 'started']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $task = $this->createTask();

        $response = $this->postJson("/api/tasks/{$task->id}/editing/start");

        $response->assertStatus(200)
            ->assertJsonPath('status', 'started');

        $task->refresh();
        $this->assertEquals('editing', $task->status);
        $this->assertEquals('active', $task->editing_status);
        $this->assertNotNull($task->editing_started_at);
        $this->assertNotNull($task->editing_expires_at);
    }

    public function test_start_editing_with_custom_url(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('startInteractiveTask')
            ->once()
            ->with(
                Mockery::on(fn($url) => $url === 'https://example.com/login'),
                Mockery::any(),
                Mockery::any()
            )
            ->andReturn(['status' => 'started']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $task = $this->createTask();

        $response = $this->postJson("/api/tasks/{$task->id}/editing/start", [
            'url' => 'https://example.com/login',
        ]);

        $response->assertStatus(200);
    }

    // -----------------------------------------------------------------
    // PATCH /api/tasks/{task}/editing/draft — Save draft
    // -----------------------------------------------------------------

    public function test_save_draft_updates_user_corrections(): void
    {
        $task = $this->createTask();

        $corrections = [
            'steps' => [[
                'step_order' => 0,
                'form_type' => 'target',
                'fields' => [
                    ['field_name' => 'email', 'field_selector' => '#email'],
                ],
            ]],
        ];

        $response = $this->patchJson("/api/tasks/{$task->id}/editing/draft", [
            'user_corrections' => $corrections,
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('status', 'draft_saved');

        $task->refresh();
        $this->assertEquals($corrections, $task->user_corrections);
    }

    // -----------------------------------------------------------------
    // POST /api/tasks/{task}/editing/confirm — Confirm editing
    // -----------------------------------------------------------------

    public function test_confirm_editing_creates_form_definitions(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('stopEditingSession')
            ->once()
            ->andReturn(['status' => 'ok']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $task = $this->createTask([
            'user_corrections' => [
                'steps' => [[
                    'step_order' => 0,
                    'form_type' => 'target',
                    'page_url' => 'https://example.com/form',
                    'form_selector' => '#myform',
                    'submit_selector' => '#submit',
                    'human_breakpoint' => false,
                    'fields' => [
                        [
                            'field_name' => 'email',
                            'field_selector' => '#email',
                            'field_type' => 'email',
                            'is_sensitive' => false,
                            'is_required' => true,
                            'sort_order' => 0,
                        ],
                    ],
                ]],
            ],
        ]);

        $response = $this->postJson("/api/tasks/{$task->id}/editing/confirm");

        $response->assertStatus(200)
            ->assertJsonPath('status', 'confirmed');

        $task->refresh();
        $this->assertEquals('draft', $task->status);
        $this->assertEquals('confirmed', $task->editing_status);
        $this->assertCount(1, $task->formDefinitions);

        $formDef = $task->formDefinitions->first();
        $this->assertEquals(0, $formDef->step_order);
        $this->assertEquals('target', $formDef->form_type);
        $this->assertEquals('#myform', $formDef->form_selector);
        $this->assertCount(1, $formDef->formFields);
    }

    public function test_confirm_editing_with_login_updates_task_login_fields(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('stopEditingSession')->once()->andReturn(['status' => 'ok']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $task = $this->createTask([
            'user_corrections' => [
                'steps' => [
                    [
                        'step_order' => 0,
                        'form_type' => 'login',
                        'page_url' => 'https://example.com/login',
                        'form_selector' => '#login-form',
                        'submit_selector' => '#login-btn',
                        'fields' => [],
                    ],
                    [
                        'step_order' => 1,
                        'form_type' => 'target',
                        'page_url' => 'https://example.com/form',
                        'form_selector' => '',
                        'submit_selector' => '',
                        'fields' => [],
                    ],
                ],
            ],
        ]);

        $response = $this->postJson("/api/tasks/{$task->id}/editing/confirm");

        $response->assertStatus(200);

        $task->refresh();
        $this->assertTrue($task->requires_login);
        $this->assertEquals('https://example.com/login', $task->login_url);
    }

    // -----------------------------------------------------------------
    // POST /api/tasks/{task}/editing/cancel — Cancel editing
    // -----------------------------------------------------------------

    public function test_cancel_editing_stops_session(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('stopEditingSession')
            ->once()
            ->andReturn(['status' => 'ok']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $task = $this->createTask(['editing_status' => 'active']);

        $response = $this->postJson("/api/tasks/{$task->id}/editing/cancel");

        $response->assertStatus(200)
            ->assertJsonPath('status', 'cancelled');

        $task->refresh();
        $this->assertEquals('draft', $task->status);
        $this->assertEquals('cancelled', $task->editing_status);
    }

    // -----------------------------------------------------------------
    // artisan formbot:cleanup-stale-editing-sessions
    // -----------------------------------------------------------------

    public function test_cleanup_cancels_expired_editing_sessions(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('stopEditingSession')->once();
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        // Create an expired editing session
        $expiredTask = $this->createTask([
            'editing_status' => 'active',
            'editing_expires_at' => now()->subMinutes(5),
        ]);

        // Create a non-expired session
        $activeTask = $this->createTask([
            'editing_status' => 'active',
            'editing_expires_at' => now()->addMinutes(15),
        ]);

        Artisan::call('formbot:cleanup-stale-editing-sessions');

        $expiredTask->refresh();
        $this->assertEquals('cancelled', $expiredTask->editing_status);
        $this->assertEquals('draft', $expiredTask->status);

        $activeTask->refresh();
        $this->assertEquals('active', $activeTask->editing_status);
    }

    public function test_cleanup_does_nothing_when_no_expired_sessions(): void
    {
        $this->createTask(['editing_status' => 'idle']);
        $this->createTask(['editing_status' => 'confirmed']);

        $exitCode = Artisan::call('formbot:cleanup-stale-editing-sessions');

        $this->assertEquals(0, $exitCode);
        $this->assertStringContainsString('No expired editing sessions found', Artisan::output());
    }
}
