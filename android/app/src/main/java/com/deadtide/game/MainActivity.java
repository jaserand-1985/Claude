package com.deadtide.game;

import android.graphics.Rect;
import android.os.Bundle;
import android.view.View;

import java.util.Arrays;
import android.view.WindowManager;

import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Keep the screen on during play.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        enterImmersive();
        // Steering is a sideways drag, so keep Android's edge "back" swipe from stealing it
        // where thumbs usually are (Android allows up to 200dp of each edge to be excluded).
        View root = getWindow().getDecorView();
        root.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> {
            float d = getResources().getDisplayMetrics().density;
            int w = r - l, h = b - t, band = (int) (200 * d), edge = (int) (40 * d), bottom = h - (int) (60 * d);
            ViewCompat.setSystemGestureExclusionRects(v, Arrays.asList(
                new Rect(0, bottom - band, edge, bottom), new Rect(w - edge, bottom - band, w, bottom)));
        });
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) enterImmersive();
    }

    // Hide the status and navigation bars; a swipe from the edge shows them briefly.
    private void enterImmersive() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat c = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        c.hide(WindowInsetsCompat.Type.systemBars());
        c.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }
}
