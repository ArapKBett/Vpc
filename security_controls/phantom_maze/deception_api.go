// AEGIS-SHIELD :: Phantom Maze :: Deception Management API
// Path: /security_controls/phantom_maze/deception_api.go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

const (
	CODENAME = "DECEPTION-CONTROL"
	VERSION  = "1.4-DEC"
)

type Attacker struct {
	IP           string    `json:"ip"`
	FirstSeen    time.Time `json:"first_seen"`
	LastSeen     time.Time `json:"last_seen"`
	Attempts     int       `json:"attempts"`
	Services     []string  `json:"services"`
	Credentials  []string  `json:"credentials"`
}

type DeceptionAPI struct {
	attackers map[string]*Attacker
	mu        sync.Mutex
}

func NewDeceptionAPI() *DeceptionAPI {
	return &DeceptionAPI{
		attackers: make(map[string]*Attacker),
	}
}

func (api *DeceptionAPI) HandleAttack(w http.ResponseWriter, r *http.Request) {
	var attack struct {
		IP          string `json:"ip"`
		Service     string `json:"service"`
		Credentials string `json:"credentials"`
	}

	if err := json.NewDecoder(r.Body).Decode(&attack); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	api.mu.Lock()
	defer api.mu.Unlock()

	attacker, exists := api.attackers[attack.IP]
	if !exists {
		attacker = &Attacker{
			IP:        attack.IP,
			FirstSeen: time.Now(),
			Services:  []string{},
		}
		api.attackers[attack.IP] = attacker
	}

	attacker.LastSeen = time.Now()
	attacker.Attempts++
	attacker.Services = appendIfMissing(attacker.Services, attack.Service)
	attacker.Credentials = append(attacker.Credentials, attack.Credentials)

	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "Attack logged")
}

func (api *DeceptionAPI) GetAttackers(w http.ResponseWriter, r *http.Request) {
	api.mu.Lock()
	defer api.mu.Unlock()

	json.NewEncoder(w).Encode(api.attackers)
}

func appendIfMissing(slice []string, s string) []string {
	for _, item := range slice {
		if item == s {
			return slice
		}
	}
	return append(slice, s)
}

func main() {
	fmt.Printf("Starting %s (v%s)\n", CODENAME, VERSION)
	api := NewDeceptionAPI()

	http.HandleFunc("/log", api.HandleAttack)
	http.HandleFunc("/attackers", api.GetAttackers)

	log.Println("Deception API listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
