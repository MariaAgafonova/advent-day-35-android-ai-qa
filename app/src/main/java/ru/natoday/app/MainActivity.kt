package ru.natoday.app

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import ru.natoday.app.reminders.ReminderScheduler
import ru.natoday.app.ui.*
import java.time.LocalDate
import java.util.Locale

class MainActivity : ComponentActivity() {
    private var reviewDay by mutableStateOf<Long?>(null)
    override fun attachBaseContext(newBase: Context) {
        val configuration = Configuration(newBase.resources.configuration)
        configuration.setLocale(Locale.forLanguageTag("ru"))
        super.attachBaseContext(newBase.createConfigurationContext(configuration))
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) readReviewIntent(intent)
        enableEdgeToEdge()
        val app = application as PlannerApplication
        setContent {
            PlannerTheme {
                PlannerNavigation(app, reviewDay) { reviewDay = null }
            }
        }
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        readReviewIntent(intent)
    }
    private fun readReviewIntent(intent: Intent) {
        if (intent.action != ReminderScheduler.ACTION_REVIEW || !intent.hasExtra(ReminderScheduler.EXTRA_DAY)) return
        val epoch = intent.getLongExtra(ReminderScheduler.EXTRA_DAY, 0)
        val date = runCatching { LocalDate.ofEpochDay(epoch) }.getOrNull() ?: return
        if (date.year in 1..9999) reviewDay = epoch
    }
}

@Composable
private fun PlannerNavigation(app: PlannerApplication, reviewDay: Long?, consume: () -> Unit) {
    val nav = rememberNavController()
    val dayVm: DayViewModel = viewModel(factory = viewModelFactory {
        initializer { DayViewModel(app.tasks, createSavedStateHandle()) }
    })
    AppClockEffect(dayVm, app)
    NavHost(navController = nav, startDestination = "today") {
        composable("today") {
            DayScreen(dayVm, onSettings = { nav.navigate("settings") }, onReview = { nav.navigate("review/" + it.toEpochDay()) }, onVoice = { nav.navigate("voice/" + it.toEpochDay()) })
        }
        composable("review/{day}", arguments = listOf(navArgument("day") { type = NavType.LongType })) { entry ->
            val vm: ReviewViewModel = viewModel(factory = viewModelFactory {
                initializer { ReviewViewModel(app.tasks, LocalDate.ofEpochDay(entry.arguments!!.getLong("day")), createSavedStateHandle()) }
            })
            ReviewScreen(vm) { nav.popBackStack() }
        }
        composable("voice/{day}", arguments = listOf(navArgument("day") { type = NavType.LongType })) { entry ->
            val vm: VoiceViewModel = viewModel(factory = viewModelFactory {
                initializer { VoiceViewModel(app.tasks, LocalDate.ofEpochDay(entry.arguments!!.getLong("day")), createSavedStateHandle()) }
            })
            VoiceScreen(vm) { nav.popBackStack() }
        }
        composable("settings") {
            val vm: SettingsViewModel = viewModel(factory = viewModelFactory { initializer { SettingsViewModel(app.settings, app.reminders) } })
            SettingsScreen(vm, app.reminders) { nav.popBackStack() }
        }
    }
    LaunchedEffect(reviewDay) {
        reviewDay?.let {
            nav.navigate("review/" + it) { popUpTo("today"); launchSingleTop = true }
            consume()
        }
    }
}
