#include "Bluetooth/CompanionControl.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using ETrackCompanion::Control;
static const std::string session(32, 'a'), nonce(32, 'b'), package(64, 'c'), target(64, 'd');
static void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }

struct Fixture
{
    std::vector<std::string> sent;
    bool allowSend;
    Control control;
    Fixture() : allowSend(true), control(Send, this) {}
    static bool Send(void* self, const char* bytes, unsigned count)
    {
        Fixture* f = static_cast<Fixture*>(self);
        if (!f->allowSend) return false;
        f->sent.push_back(std::string(bytes, count));
        return true;
    }
    static std::string Frame(const std::string& body)
    {
        char suffix[8];
        snprintf(suffix, sizeof(suffix), "*%04x\n", Control::Crc(body.data(), (unsigned)body.size()));
        return body + suffix;
    }
    void Feed(const std::string& bytes, uint32_t tick = 10)
    {
        for (unsigned char byte : bytes) control.Feed(byte, tick);
    }
    void Message(const std::string& kind, unsigned request, const std::string& fields = "", uint32_t tick = 10)
    { Feed(Frame("!ETC1|" + kind + "|" + session + "|" + std::to_string(request) + fields), tick); }
    void Hello() { Message("HELLO", 0); }
    void Offer(unsigned request = 0, uint32_t tick = 10, const std::string& id = nonce)
    { Message("OFFER", request, "|" + id + "|30328|" + package + "|" + target + "|1", tick); }
    bool Status(const char* expected) { return strcmp(control.Info().status, expected) == 0; }
};

static void Test(const std::string& name)
{
    Fixture f;
    if (name == "crc") {
        require(Control::Crc("123456789", 9) == 0x29b1, "CCITT-FALSE mismatch");
        f.Hello();
        require(f.sent.at(0) == Fixture::Frame("!ETC1|CAPS|" + session + "|0|1"), "CAPS wire format");
    } else if (name == "phone_missing") {
        require(!f.control.Check(10) && f.Status("PHONE_REQUIRED") && f.sent.empty(), "absent phone must not check");
    } else if (name == "check_timeout") {
        f.Hello(); require(f.control.Check(20), "check start");
        require(!f.control.Check(21), "inflight check coalesced");
        f.control.Poll(10019, false); require(f.control.Info().checking, "too early timeout");
        f.control.Poll(10020, false); require(f.Status("PHONE_REQUIRED") && !f.control.Info().checking, "phone timeout");
    } else if (name == "acknowledged_timeout") {
        f.Hello(); f.control.Check(20); f.Message("STATE", 1, "|CHECKING", 100);
        f.control.Poll(120099, false); require(f.control.Info().checking, "checking wait shortened");
        f.control.Poll(120100, false); require(!f.control.Info().checking, "checking wait unbounded");
    } else if (name == "starting_timeout") {
        f.Hello(); f.Offer(); f.control.Choose(true, 20);
        f.Message("STATE", 0, "|STARTING", 100);
        f.control.Poll(120100, false);
        require(f.Status("PHONE_REQUIRED") && !f.control.Info().checking, "failed background start traps the menu");
        require(f.control.Check(120101), "cannot retry after refused start");
    } else if (name == "binary_end_recovers_menu") {
        f.Hello(); f.Offer(); f.control.Poll(20, true); f.control.Poll(30, false);
        require(f.Status("PHONE_REQUIRED") && !f.control.Info().hasOffer, "binary abort traps the menu");
        require(f.control.Check(31), "cannot check after binary end");
    } else if (name == "download_timeout") {
        f.Hello(); f.control.Check(20); f.Message("STATE", 1, "|DOWNLOADING", 100);
        f.control.Poll(600099, false); require(f.control.Info().checking, "download wait shortened");
        f.control.Poll(600100, false); require(!f.control.Info().checking, "download wait unbounded");
    } else if (name == "timer_wrap") {
        f.Hello(); require(f.control.Check(0xfffffff0u), "wrap check start");
        f.control.Poll(9983, false); require(f.control.Info().checking, "wrap timeout too early");
        f.control.Poll(9984, false); require(!f.control.Info().checking, "wrap timeout missing");
    } else if (name == "offer_choice_once") {
        f.Hello(); f.Offer();
        require(f.control.Info().hasOffer && f.control.Info().prompt, "valid offer not ready");
        f.control.Presented(); require(!f.control.Info().prompt, "shown still prompts");
        require(f.sent.back().find("|SHOWN|") != std::string::npos, "missing display receipt");
        require(f.control.Choose(true, 20), "confirmed choice rejected");
        require(f.sent.back().find("|NOW*") != std::string::npos, "not a NOW choice");
        const auto count = f.sent.size();
        f.Offer(0, 21); require(!f.control.Choose(true, 22), "replayed offer rearmed consent");
        require(f.sent.size() == count, "replay caused TX");
    } else if (name == "later_never_installs") {
        f.Hello(); f.Offer(); require(f.control.Choose(false, 20), "later rejected");
        require(f.Status("DEFERRED") && !f.control.Info().hasOffer && !f.control.Info().checking, "later state");
        require(f.sent.back().find("|LATER*") != std::string::npos, "later encoded incorrectly");
    } else if (name == "duplicate_expiry") {
        f.Hello(); f.Offer(0, 10); f.Offer(0, 299999);
        f.control.Poll(300010, false);
        require(!f.control.Info().hasOffer && !f.control.Choose(true, 300011), "duplicate extends consent");
        f.Offer(0, 300012); require(!f.control.Info().hasOffer, "expired offer reused");
    } else if (name == "display_binding") {
        f.Hello(); f.Offer(); auto display = f.control.Info();
        require(f.control.Matches(&display), "current display mismatch");
        f.Offer(0, 20, std::string(32, 'e'));
        require(!f.control.Matches(&display), "stale display accepted");
        display = f.control.Info(); display.targetSha256[0] = 'f';
        require(!f.control.Matches(&display), "different target accepted");
    } else if (name == "binary_exclusion") {
        f.Hello(); f.Offer(); f.control.Poll(20, true); const auto count = f.sent.size();
        f.Hello(); require(!f.control.Check(21) && !f.control.Choose(true, 21), "binary owner lost exclusion");
        require(f.sent.size() == count && !f.control.Info().hasOffer, "control during binary TX");
        f.control.Poll(30, false); f.Hello(); require(f.control.Check(31), "text did not recover");
    } else if (name == "malformed") {
        f.Hello(); const auto count = f.sent.size();
        for (const auto& body : std::vector<std::string>{
            "!ETC2|HELLO|" + session + "|0", "!ETC1|HELLO|" + session + "|00",
            "!ETC1|HELLO|" + session + "|4294967296", "!ETC1|HELLO|" + session + "|0|extra",
            "!ETC1|OFFER|" + session + "|0|" + nonce + "|2100000001|" + package + "|" + target + "|1",
            "!ETC1|STATE|" + session + "|0|UNKNOWN"}) f.Feed(Fixture::Frame(body));
        auto corrupt = Fixture::Frame("!ETC1|HELLO|" + session + "|0"); corrupt[8] = 'X'; f.Feed(corrupt);
        require(f.sent.size() == count && !f.control.Info().hasOffer, "malformed message changed state");
    } else if (name == "parser_recovery") {
        f.Feed("!" + std::string(400, 'a'));
        f.Message("HELLO", 0, "", 2011); require(f.Status("CONNECTED"), "overlong timeout swallowed next frame");
        f.control.Poll(3000, true); f.control.Poll(3001, false); f.Hello();
        require(f.sent.size() == 2, "partial/binary parser failed to reset");
    } else if (name == "periodic_after_manual") {
        f.Hello(); f.control.Check(20); f.Message("STATE", 1, "|NO_UPDATE");
        f.Message("STATE", 0, "|CHECKING"); f.Offer();
        require(f.control.Info().hasOffer && f.control.Info().request == 0, "periodic result rejected after manual request");
    } else if (name == "stale_session_and_request") {
        f.Hello(); f.control.Check(20); f.Offer(2); f.Offer(0);
        require(!f.control.Info().hasOffer, "wrong request accepted");
        f.Feed(Fixture::Frame("!ETC1|STATE|" + std::string(32, 'e') + "|1|NO_UPDATE"));
        require(f.control.Info().checking, "old session changed status");
        f.Message("STATE", 1, "|FAILED"); require(f.Status("FAILED"), "error became latest");
    } else if (name == "send_failure") {
        f.Hello(); f.allowSend = false;
        require(!f.control.Check(20) && f.Status("PHONE_REQUIRED"), "failed check TX hidden");
        f.allowSend = true; f.Offer(); f.allowSend = false;
        require(!f.control.Choose(true, 30) && f.control.Info().hasOffer, "failed choice consumed consent");
    } else if (name == "all_display_fields") {
        f.Hello(); f.Offer(); const auto display = f.control.Info();
        for (unsigned field = 0; field < 8; ++field) {
            auto changed = display;
            switch (field) {
                case 0: ++changed.version; break;
                case 1: ++changed.request; break;
                case 2: changed.session[0] = 'e'; break;
                case 3: changed.offer[0] = 'e'; break;
                case 4: changed.packageSha256[0] = 'e'; break;
                case 5: changed.targetSha256[0] = 'e'; break;
                case 6: ++changed.offerRevision; break;
                case 7: changed.hasOffer = false; break;
            }
            require(!f.control.Matches(&changed), "changed display field accepted");
        }
    } else if (name == "offer_revision_reappearance") {
        f.Hello(); f.Offer(); const auto first = f.control.Info();
        f.Offer(0, 20); require(f.control.Matches(&first), "exact retransmission cancelled display");
        f.Offer(0, 30, std::string(32, 'e')); f.Offer(0, 40);
        require(!f.control.Matches(&first), "A-B-A replacement reused an old interaction");
    } else if (name == "reservation_timeout" || name == "reservation_wrap") {
        const uint32_t start = name == "reservation_wrap" ? 0xfffffff0u : 20u;
        f.Hello(); f.Offer(0, start);
        require(f.control.Choose(true, start), "NOW rejected");
        require(f.control.InstallPending(start + 119999u), "reservation ended early");
        f.Message("STATE", 0, "|STARTING", start + 119999u);
        require(!f.control.InstallPending(start + 120000u), "remote state extended reservation");
        require(!f.control.Info().checking && f.control.Check(start + 120001u), "expired reservation trapped retry");
    } else if (name == "reservation_cleanup") {
        for (unsigned mode = 0; mode < 5; ++mode) {
            Fixture item; item.Hello(); item.Offer();
            require(item.control.Choose(true, 20) && item.control.InstallPending(21), "reservation not created");
            if (mode == 0) item.Message("STATE", 0, "|FAILED", 30);
            if (mode == 1) item.Feed(Fixture::Frame("!ETC1|HELLO|" + std::string(32, 'e') + "|0"), 30);
            if (mode == 2) item.Offer(0, 30, std::string(32, 'e'));
            if (mode == 3) item.control.Poll(30, true);
            if (mode == 4) item.control.CancelInstall();
            require(!item.control.InstallPending(31), "reservation leaked after termination/replacement");
        }
    } else if (name == "reservation_failed_send") {
        f.Hello(); f.Offer(); f.allowSend = false;
        require(!f.control.Choose(true, 20) && !f.control.InstallPending(21), "failed NOW reserved installation");
        f.allowSend = true;
        require(f.control.Choose(false, 22) && !f.control.InstallPending(23), "LATER reserved installation");
    } else { throw std::runtime_error("unknown test case"); }
}

int main(int argc, char** argv)
{
    try {
        require(argc == 2, "test name required"); Test(argv[1]);
        std::cout << argv[1] << ": PASS\n"; return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
