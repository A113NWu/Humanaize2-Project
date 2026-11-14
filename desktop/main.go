package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/egoist/mygo"
)

// defaultDashboard is the local Humanaize2 web dashboard.
const defaultDashboard = "http://127.0.0.1:8082/"

// waitUntilReachable polls url until it returns a 2xx or the timeout fires.
func waitUntilReachable(url string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	client := &http.Client{Timeout: 2 * time.Second}
	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode < 500 {
				return true
			}
		}
		time.Sleep(400 * time.Millisecond)
	}
	return false
}

func main() {
	dashboardURL := defaultDashboard
	if len(os.Args) > 1 && os.Args[1] != "" {
		dashboardURL = os.Args[1]
	}
	// 0.0.0.0 is a listen address, not a connectable one: WebView2 would fail.
	dashboardURL = strings.Replace(dashboardURL, "//0.0.0.0", "//127.0.0.1", 1)

	mygo.App.WhenReady(func() {
		win := mygo.NewWindow(mygo.WindowOptions{
			Title:     "Humanaize2",
			Width:     1280,
			Height:    800,
			MinWidth:  1000,
			MinHeight: 600,
			StateKey:  "humanaize2-main",
			// The page draws its own background, so keep the window plain.
			BackgroundColor: "#0b1218",
			URL:             dashboardURL,
		})

		// If the backend is still warming up, wait until it answers, then
		// (re)load the dashboard so the window never shows a blank error page.
		go func() {
			if waitUntilReachable(dashboardURL, 60*time.Second) {
				_ = win.Page().LoadURL(dashboardURL)
			} else {
				log.Printf("[WARN] dashboard not reachable within timeout: %s", dashboardURL)
			}
		}()
	})

	if err := mygo.App.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
