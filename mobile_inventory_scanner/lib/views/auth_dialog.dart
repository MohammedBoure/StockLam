// mobile_inventory_scanner/lib/views/auth_dialog.dart

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api_client.dart';
import '../models.dart';

const savedAccountsKey = 'modernstock_saved_accounts';
const activeAccountIdKey = 'modernstock_active_account_id';

class AccountStorage {
  static Future<List<SavedAccount>> loadSavedAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(savedAccountsKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => SavedAccount.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> saveAccount(SavedAccount account) async {
    final prefs = await SharedPreferences.getInstance();
    final accounts = await loadSavedAccounts();
    accounts.removeWhere((a) => a.id == account.id || (a.serverUrl == account.serverUrl && a.username == account.username));
    accounts.insert(0, account);
    final raw = jsonEncode(accounts.map((a) => a.toJson()).toList());
    await prefs.setString(savedAccountsKey, raw);
    await prefs.setString(activeAccountIdKey, account.id);
  }

  static Future<void> removeAccount(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final accounts = await loadSavedAccounts();
    accounts.removeWhere((a) => a.id == id);
    final raw = jsonEncode(accounts.map((a) => a.toJson()).toList());
    await prefs.setString(savedAccountsKey, raw);
    final active = prefs.getString(activeAccountIdKey);
    if (active == id) {
      await prefs.remove(activeAccountIdKey);
    }
  }

  static Future<String?> getActiveAccountId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(activeAccountIdKey);
  }

  static Future<void> setActiveAccountId(String? id) async {
    final prefs = await SharedPreferences.getInstance();
    if (id == null) {
      await prefs.remove(activeAccountIdKey);
    } else {
      await prefs.setString(activeAccountIdKey, id);
    }
  }
}

class LoginDialog extends StatefulWidget {
  const LoginDialog({
    super.key,
    required this.api,
    required this.serverName,
    required this.serverUrl,
    this.initialUsername,
  });

  final ApiClient api;
  final String serverName;
  final String serverUrl;
  final String? initialUsername;

  @override
  State<LoginDialog> createState() => _LoginDialogState();
}

class _LoginDialogState extends State<LoginDialog> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _rememberMe = true;
  bool _loading = false;
  String? _errorMessage;

  List<Map<String, dynamic>> _availableUsers = [];
  List<SavedAccount> _savedAccounts = [];

  @override
  void initState() {
    super.initState();
    if (widget.initialUsername != null) {
      _usernameController.text = widget.initialUsername!;
    }
    _loadData();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final accounts = await AccountStorage.loadSavedAccounts();
    if (mounted) setState(() => _savedAccounts = accounts);

    try {
      final users = await widget.api.getUsersList();
      if (mounted) {
        setState(() {
          _availableUsers = users;
          if (_usernameController.text.isEmpty && users.isNotEmpty) {
            _usernameController.text = users.first['username'] as String? ?? '';
          }
        });
      }
    } catch (_) {}
  }

  Future<void> _performLogin() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = 'Veuillez saisir votre nom d\'utilisateur et mot de passe.');
      return;
    }

    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      final authUser = await widget.api.login(
        username: username,
        password: password,
      );

      final accountId = '${widget.serverUrl}__$username';
      final savedAcc = SavedAccount(
        id: accountId,
        serverUrl: widget.serverUrl,
        serverName: widget.serverName,
        username: username,
        password: password,
        userId: authUser.userId,
        fullName: authUser.fullName,
        role: authUser.role,
        savedAt: DateTime.now(),
      );

      if (_rememberMe) {
        await AccountStorage.saveAccount(savedAcc);
      } else {
        await AccountStorage.setActiveAccountId(accountId);
      }

      if (mounted) {
        Navigator.pop(context, savedAcc);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception:', '').trim();
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _useSavedAccount(SavedAccount account) async {
    _usernameController.text = account.username;
    _passwordController.text = account.password;
    await _performLogin();
  }

  @override
  Widget build(BuildContext context) {
    final deviceAccounts = _savedAccounts.where((a) => cleanBaseUrl(a.serverUrl) == cleanBaseUrl(widget.serverUrl)).toList();

    return AlertDialog(
      title: Row(
        children: [
          const CircleAvatar(
            backgroundColor: Color(0xFFE8F8F0),
            child: Icon(Icons.lock_person, color: Color(0xFF007572)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Connexion Utilisateur', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                Text(
                  widget.serverName,
                  style: const TextStyle(fontSize: 12, color: Colors.black54, fontWeight: FontWeight.normal),
                ),
              ],
            ),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_errorMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(8),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFDEEED),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(_errorMessage!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              ),
            ],

            if (_availableUsers.isNotEmpty) ...[
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: _availableUsers.any((u) => u['username'] == _usernameController.text)
                    ? _usernameController.text
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Sélectionner un compte',
                  prefixIcon: Icon(Icons.person),
                  isDense: true,
                ),
                items: _availableUsers.map((u) {
                  final name = u['full_name'] as String? ?? u['username'] as String? ?? '';
                  final role = u['role'] as String? ?? 'Technicien';
                  return DropdownMenuItem<String>(
                    value: u['username'] as String?,
                    child: Text('$name ($role)', overflow: TextOverflow.ellipsis),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() => _usernameController.text = val);
                  }
                },
              ),
              const SizedBox(height: 10),
            ],

            TextField(
              controller: _usernameController,
              decoration: const InputDecoration(
                labelText: 'Nom d\'utilisateur',
                prefixIcon: Icon(Icons.account_circle),
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),

            TextField(
              controller: _passwordController,
              obscureText: _obscurePassword,
              decoration: InputDecoration(
                labelText: 'Mot de passe',
                prefixIcon: const Icon(Icons.lock),
                isDense: true,
                suffixIcon: IconButton(
                  icon: Icon(_obscurePassword ? Icons.visibility : Icons.visibility_off),
                  onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                ),
              ),
              onSubmitted: (_) => _performLogin(),
            ),
            const SizedBox(height: 6),

            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('Enregistrer ce compte sur l\'appareil', style: TextStyle(fontSize: 13)),
              value: _rememberMe,
              onChanged: (val) => setState(() => _rememberMe = val ?? true),
              controlAffinity: ListTileControlAffinity.leading,
            ),

            if (deviceAccounts.isNotEmpty) ...[
              const Divider(height: 18),
              const Text('Comptes enregistrés sur ce PC :', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              ...deviceAccounts.map((acc) => ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.account_box, color: Color(0xFF007572)),
                    title: Text(acc.fullName.isNotEmpty ? acc.fullName : acc.username, style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text('${acc.role} • ${acc.username}'),
                    trailing: TextButton(
                      onPressed: _loading ? null : () => _useSavedAccount(acc),
                      child: const Text('Utiliser'),
                    ),
                  )),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, null),
          child: const Text('Annuler'),
        ),
        FilledButton(
          onPressed: _loading ? null : _performLogin,
          child: _loading
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
              : const Text('Se connecter'),
        ),
      ],
    );
  }
}

class SavedAccountsSheet extends StatelessWidget {
  const SavedAccountsSheet({
    super.key,
    required this.accounts,
    required this.activeAccountId,
    required this.onSelectAccount,
    required this.onDeleteAccount,
    required this.onAddNewLogin,
    required this.onLogout,
  });

  final List<SavedAccount> accounts;
  final String? activeAccountId;
  final ValueChanged<SavedAccount> onSelectAccount;
  final ValueChanged<String> onDeleteAccount;
  final VoidCallback onAddNewLogin;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(Icons.switch_account, color: Color(0xFF007572)),
              const SizedBox(width: 8),
              const Text('Gestion des Comptes & Appareils', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Basculez rapidement entre vos sessions et ordinateurs enregistrés.',
            style: TextStyle(color: Colors.black54, fontSize: 13),
          ),
          const Divider(height: 20),

          if (accounts.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: Text('Aucun compte enregistré.', style: TextStyle(color: Colors.black54)),
              ),
            )
          else
            Flexible(
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: accounts.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (ctx, i) {
                  final acc = accounts[i];
                  final isActive = (acc.id == activeAccountId);

                  return ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    leading: CircleAvatar(
                      backgroundColor: isActive ? const Color(0xFF27AE60) : const Color(0xFFE2E8F0),
                      foregroundColor: isActive ? Colors.white : Colors.black87,
                      child: Icon(isActive ? Icons.check : Icons.computer),
                    ),
                    title: Text(
                      '${acc.fullName.isNotEmpty ? acc.fullName : acc.username} (${acc.role})',
                      style: TextStyle(fontWeight: isActive ? FontWeight.bold : FontWeight.normal),
                    ),
                    subtitle: Text('💻 ${acc.serverName} • ${acc.serverUrl}'),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.red, size: 20),
                          tooltip: 'Supprimer ce compte',
                          onPressed: () => onDeleteAccount(acc.id),
                        ),
                        if (!isActive)
                          FilledButton.tonal(
                            onPressed: () {
                              Navigator.pop(ctx);
                              onSelectAccount(acc);
                            },
                            child: const Text('Activer'),
                          ),
                      ],
                    ),
                  );
                },
              ),
            ),

          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                  onPressed: () {
                    Navigator.pop(context);
                    onLogout();
                  },
                  icon: const Icon(Icons.logout),
                  label: const Text('Déconnexion'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  onPressed: () {
                    Navigator.pop(context);
                    onAddNewLogin();
                  },
                  icon: const Icon(Icons.add),
                  label: const Text('Nouveau Compte'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
