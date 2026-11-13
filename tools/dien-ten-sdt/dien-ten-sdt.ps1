Add-Type -AssemblyName System.Windows.Forms, System.Drawing, UIAutomationClient, UIAutomationTypes, WindowsBase
$refs = @('System.Windows.Forms', 'System.Drawing',
    [System.Windows.Automation.AutomationElement].Assembly.Location,
    [System.Windows.Automation.ControlType].Assembly.Location,
    [System.Windows.Threading.Dispatcher].Assembly.Location)
Add-Type -ReferencedAssemblies $refs -TypeDefinition @'
using System;
using System.Windows.Automation;
using System.Drawing;
using System.Threading;
using System.Windows.Forms;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

public class DienTenSdt : Form {
    [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mod, uint vk);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int vk);

    Label lb;
    string[] data; // [ten, ho, sdt]

    public DienTenSdt() {
        Text = "Điền Tên - SĐT (đóng cửa sổ này để tắt)";
        Width = 460; Height = 210; TopMost = true; ShowInTaskbar = true;
        StartPosition = FormStartPosition.Manual;
        var wa = Screen.PrimaryScreen.WorkingArea;
        Location = new Point(wa.Right - Width - 10, wa.Bottom - Height - 10);
        lb = new Label { Dock = DockStyle.Fill, Font = new Font("Segoe UI", 10), Padding = new Padding(8) };
        Controls.Add(lb);
        ShowStatus("Chưa có dữ liệu. Hãy copy thông tin (Name, Phone) trước.");
    }

    protected override void OnLoad(EventArgs e) {
        base.OnLoad(e);
        for (int i = 1; i <= 3; i++) RegisterHotKey(Handle, i, 0x1 | 0x4000, (uint)(0x30 + i)); // Alt+1..3
        RegisterHotKey(Handle, 4, 0x1 | 0x4000, 0x56); // Alt+V = điền cả 3 ô
        RegisterHotKey(Handle, 5, 0x1 | 0x4000, 0x43); // Alt+C = tự copy trang thông tin
    }

    // Số lần Tab từ ô Achternaam tới ô Telefoonnummer (Email, Land/regio, NL +31, rồi tới ô số)
    const int TAB_TOI_SDT = 4;
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();

    static void Go(string keys) { SendKeys.SendWait(keys); Thread.Sleep(150); }

    // Dán giá trị thay vì gõ phím -> bộ gõ tiếng Việt (Unikey/EVKey) không làm sai chữ
    static void Paste(string v) {
        for (int k = 0; k < 5; k++) { try { Clipboard.SetText(v); break; } catch { Thread.Sleep(50); } }
        Go("^a"); Go("^v");
    }

    // Tìm ô tích có chữ "account"/"konto" (Update mijn account..., Update my account...) và tích nó
    public static string TickAccount(IntPtr hwnd) {
        for (int k = 0; k < 8; k++) {
            try {
                var root = AutomationElement.FromHandle(hwnd);
                var cbs = root.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.CheckBox));
                foreach (AutomationElement cb in cbs) {
                    string n = (cb.Current.Name ?? "").ToLower();
                    if (!(n.Contains("account") || n.Contains("konto"))) continue;
                    object p;
                    if (cb.TryGetCurrentPattern(TogglePattern.Pattern, out p)) {
                        var tp = (TogglePattern)p;
                        if (tp.Current.ToggleState != ToggleState.On) tp.Toggle();
                        return "ok";
                    }
                    if (cb.TryGetCurrentPattern(InvokePattern.Pattern, out p)) { ((InvokePattern)p).Invoke(); return "ok"; }
                }
            } catch { }
            Thread.Sleep(300); // Chrome bật trợ năng lần đầu cần chút thời gian
        }
        return "khong thay";
    }

    // Bấm nút chuyển bước: "Volgende stap..." / "Next step..."
    public static string ClickNext(IntPtr hwnd) {
        string[] kw = { "volgende stap", "next step" };
        var cond = new OrCondition(
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button),
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Hyperlink));
        for (int k = 0; k < 8; k++) {
            try {
                var all = AutomationElement.FromHandle(hwnd).FindAll(TreeScope.Descendants, cond);
                foreach (AutomationElement b in all) {
                    string n = (b.Current.Name ?? "").ToLower();
                    if (!Array.Exists(kw, x => n.Contains(x))) continue;
                    object p;
                    if (b.TryGetCurrentPattern(InvokePattern.Pattern, out p)) { ((InvokePattern)p).Invoke(); return "ok"; }
                }
            } catch { }
            Thread.Sleep(300);
        }
        return "khong thay";
    }

    protected override void OnFormClosed(FormClosedEventArgs e) {
        for (int i = 1; i <= 5; i++) UnregisterHotKey(Handle, i);
        base.OnFormClosed(e);
    }

    void ShowStatus(string msg) {
        string d = data == null ? "(trống)" :
            "Tên (Voornaam): " + data[0] + "\nHọ (Achternaam): " + data[1] + "\nSĐT: " + data[2];
        lb.Text = d + "\n\nTrang thông tin: Alt+C = tự copy\nForm: bấm ô Voornaam rồi Alt+V = điền cả 3 ô\n(Alt+1 Tên, Alt+2 Họ, Alt+3 SĐT: gõ từng ô)\n" + msg;
    }

    public static string ToNational(string p) {
        // bỏ phần máy lẻ: "ext 12", "x12", "toestel 12"
        p = Regex.Replace(p, @"(?i)\s*(ext\.?|x|toestel|tst\.?)\s*\d+\s*$", "");
        string d = Regex.Replace(p, @"\D", "");          // chỉ giữ chữ số
        bool intl = Regex.IsMatch(p, @"^\W*(\+|00)") || (d.StartsWith("31") && d.Length >= 11);
        if (intl) d = Regex.Replace(d, @"^(00)?31", ""); // +31 / 0031 / 31...
        d = d.TrimStart('0');                             // +31 (0)16... hoặc 0016...
        d = "0" + d;
        if (d.Length == 10) d = d.Substring(0, 3) + " " + d.Substring(3, 3) + " " + d.Substring(6);
        return d;
    }

    // Nhận: "Xavi|Bertho|042 967 5490"  hoặc  bảng copy có "Name ... Phone ..."
    public static string[] Parse(string s) {
        if (string.IsNullOrWhiteSpace(s)) return null;
        var parts = s.Trim().Split('|');
        if (parts.Length >= 3) return new[] { parts[0].Trim(), parts[1].Trim(), parts[2].Trim() };
        var mn = Regex.Match(s, @"(?im)(?:^|\t)[ ]*(?:Full Name|Name|Naam)[ ]*[:\t\r\n]+[ ]*([^\t\r\n]+)");
        // lấy cả ô giá trị sau nhãn Phone (mọi định dạng), cần ít nhất 7 chữ số
        Match mp = Match.Empty;
        foreach (Match x in Regex.Matches(s, @"(?im)(?:^|\t)[  ]*(?:Phone Number|Phone|Telephone|Tel|Mobile|Mobiel|Telefoon(?:nummer)?)[  ]*[:\t\r\n]+[  ]*([^\t\r\n]+)"))
            if (Regex.Replace(x.Groups[1].Value, @"\D", "").Length >= 7) { mp = x; break; }
        if (!mn.Success || !mp.Success) return null;
        var name = Regex.Split(mn.Groups[1].Value.Trim(), @"\s+");
        name = new[] { name[0], string.Join(" ", name, 1, name.Length - 1) };
        return new[] { name[0], name.Length > 1 ? name[1] : "", ToNational(mp.Groups[1].Value.Trim()) };
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == 0x0312 && (int)m.WParam == 5) {
            while ((GetAsyncKeyState(0x12) & 0x8000) != 0) Thread.Sleep(20); // chờ nhả Alt
            try { Clipboard.Clear(); } catch { }
            Go("^a"); Go("^c"); Thread.Sleep(250);
            string all = "";
            try { all = Clipboard.GetText(); } catch { }
            Go("{ESC}");
            var d = Parse(all);
            if (d != null) { data = d; ShowStatus("✔ Đã copy xong. Sang form: bấm ô Voornaam rồi Alt+V."); }
            else ShowStatus("⚠ Không thấy Name/Phone. Bấm chuột vào giữa trang rồi Alt+C lại.");
        }
        else if (m.Msg == 0x0312) {
            int id = (int)m.WParam;
            string clip = "";
            try { clip = Clipboard.GetText(); } catch { }
            var d = Parse(clip);
            if (d != null) data = d;      // clipboard mới hợp lệ -> cập nhật
            if (data == null) { ShowStatus("⚠ Clipboard chưa có Name/Phone."); }
            else {
                while ((GetAsyncKeyState(0x12) & 0x8000) != 0) Thread.Sleep(20); // chờ nhả phím Alt
                if (id == 4) {
                    IntPtr win = GetForegroundWindow();
                    Paste(data[0]);
                    Go("{TAB}"); Paste(data[1]);
                    Go("{TAB " + TAB_TOI_SDT + "}"); Paste(data[2]);
                    Go("{TAB}"); // rời ô số để trang kiểm tra hợp lệ
                    string r = TickAccount(win);
                    try { Clipboard.SetText(data[0] + "|" + data[1] + "|" + data[2]); } catch { }
                    Thread.Sleep(400); // chờ trang kiểm tra hợp lệ xong
                    string nx = ClickNext(win);
                    ShowStatus("✔ Đã điền 3 ô." +
                        (r == "ok" ? " ✔ Tích ô Update." : " ⚠ Không thấy ô Update.") +
                        (nx == "ok" ? " ✔ Bấm Volgende stap." : " ⚠ Không thấy nút Volgende stap."));
                } else {
                    Paste(data[id - 1]);
                    ShowStatus("✔ Đã gõ: " + data[id - 1]);
                }
            }
        }
        base.WndProc(ref m);
    }
}
'@
if ($args -contains '-test') { return }
$mutex = New-Object System.Threading.Mutex($false, 'DienTenSdt_DangChay')
if (-not $mutex.WaitOne(0)) {
    [System.Windows.Forms.MessageBox]::Show('Chương trình đang chạy rồi (cửa sổ nhỏ ở góc phải dưới màn hình).', 'Điền Tên - SĐT') | Out-Null
    return
}
[System.Windows.Forms.Application]::Run((New-Object DienTenSdt))
